# PO Agent — Claude Code workflow (MVP build)

**Version:** v5.8 · 16 Oct 2026 · **Owner:** Joey Wu

**Approach:** Addy Osmani's agent-skills as the main workflow, phase by phase as in its greenfield tutorial (Define → Plan → Build → Verify → Review → Ship), plus one Matt Pocock skill, `improve-codebase-architecture`, used after the MVP. CLAUDE.md, hooks, one check command and CI on GitHub keep it safe. The MVP runs on the office Mac Mini against the test site (`SPEC.md`; CEO decision 3).

**v5.8:** Stage 3B collects the **3 most recent** real PO PDFs for the MVP (10–20 before go-live).

**v5.7:** Part 4 ends with **Solved**: the test site has no Resolve button. Stage 3A gets rows 15–18 for the screens off the happy path: a Note back to the pool, a project search with no match (moved out of row 06), a Create New Task error, and a cancelled task (was row 07b).

**v5.6:** Stage 3 (M0) rewritten as the SOP in four parts (check the PO email, create the task, fill in the form, link and resolve), with the six checks marked on the rows where they come up. Also: "Done means" lines on the 3D, 4.1 and Stage 5 prompts, and a "When to clear context" table in Stage 5.

**v5.5:** CEO decision 3: the MVP trial and production run on the **office Mac Mini**, not an Anthropic cloud routine. Stage 5 sets it up with `docs/macmini-setup.md` (replaces `docs/routine-setup.md`); Stage 6.3 and Stage 7 use `launchctl kickstart` and `runs.log` instead of **Run now** and transcripts.

**v5.4:** the GitHub CLI is already installed (portable zip in `C:\Users\JoeyWu\tools\gh\bin`, v2.102.0) and logged in as **PromptEngineeringAI01** with the scopes the workflow needs, so Stage 0 skips installing and logging in, and adds `gh auth setup-git`, an account check and a line for IT.

**v5.3:** the demo is repeatable (at least 3 times): `docs/demo-runbook.md` has the 10-minute reset, two ways to show it, and what to point out.

**What changed in v5.2:** the spec is approved; the test site is reset by **cancelling** tasks with your own account (Stage 6.1), and the test profile's duplicate check ignores Cancelled tasks; Pro plan noted; Node.js confirmed, so Playwright CLI is the path.

**v5.1:**

- **Screens are mapped with Playwright CLI** (`@playwright/cli`): you click, Claude Code takes the accessibility snapshot and screenshot of each screen and writes the screen map. No recording file to make, and the planned `po-agent capture` command is dropped. The classic recorder (`playwright codegen`) stays as the fallback (Stage 3A, end).
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
| Ship | `documentation-and-adrs` | **Yes** | Decision entries; a new ADR for any later hosting or design change (ADR-002 is Accepted: the Mac Mini) |
| Ship | `observability-and-instrumentation` | Light | M5 (run output, alerts); v1 alerts |
| Ship | `shipping-and-launch` (`/ship`) | **Yes** | Before the MVP demo (M6); before production |
| Ship | `deprecation-and-migration` | Later | Moving off the Mac Mini, if that's ever needed |
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
| GitHub or local? | **Private GitHub repo.** Required: the Mac Mini pulls `main` from GitHub and opens alert issues there. Get the OK from CEO/IT (no real client data and no credentials in it). | The Mac Mini, CI on every push, PRs for review. |
| Where's the plan? | `tasks/plan.md` and `tasks/todo.md`, written by `/plan`. | The skills' default; `/build` reads them. |
| Parallel agents / worktrees? | **No.** Tasks run in order. | Serial chain; easier to trust the guard. |
| Hooks? | **Yes, created in M1**, then changed only by Joey. | Must-never rules enforced in code, not advice. |
| Evals? | **The seam 1 fixture set is the eval suite**, plus the real-PO set on the laptop. Every bug adds a fixture. | Proves "zero false PROCEED". |
| Freeze point? | When `tasks/plan.md` is approved. After that, a behaviour change needs a dated `docs/decisions.md` entry plus `SPEC.md` and `tasks/plan.md` in the same commit. | Keeps the audit trail honest. |
| Where does work happen? | Claude Code in the VS Code terminal, in the repo folder. The Mac Mini only runs the finished script (no Claude Code there). The claude.ai project keeps the CEO brief and doc copies. | |

## Source of truth per artifact

| Artifact | Source of truth | Copies |
|---|---|---|
| Spec, intent, decisions, ADRs, workflow, Mac Mini setup | **Repo** (`SPEC.md`, `docs/`) | claude.ai project copies, headed `Synced from <commit SHA>` |
| CEO decisions 1, 2, 3 | **CEO decision brief** in the claude.ai project | `docs/decisions.md` records date and outcome |
| Plan and tasks | `tasks/plan.md`, `tasks/todo.md` | — |
| Run output | `~/Library/Logs/po-agent/runs.log` on the Mac Mini; `logs/` on the laptop (git-ignored); the Mac Mini's `state_dir` in v1 | Never in the repo or the claude.ai project |
| Real client data | `private/` on Joey's laptop (git-ignored) | Nowhere else |
| Credentials | keyring: Windows Credential Manager on the laptop; `poagent`'s login Keychain on the Mac Mini | Nowhere else |

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

**Which account owns the repo:** `gh repo create` in Stage 1 creates it under **PromptEngineeringAI01**. That's right if it's the company's account for this work. If the company has a GitHub *organisation* instead, create it there (Stage 1 shows how). Whichever you choose, create the Mac Mini's fine-grained token on **the same account** (`docs/macmini-setup.md` section 1), or the Mac Mini can't pull the repo.

**The zip version doesn't update itself.** To update later, download the new Windows zip from github.com/cli/cli/releases and replace the contents of `C:\Users\JoeyWu\tools\gh`. Not needed now.

**Get the OK:** one email to the CEO/IT: *"OK to keep the PO Agent code in a private GitHub repo (account PromptEngineeringAI01) and have the office Mac Mini pull it to run the agent? No real client data and no credentials go in it. To do this I've installed the GitHub CLI (portable version, in my user folder, no admin rights) and signed it in to that account."*

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

## Stage 3 — M0: book one PO by hand while Claude watches (about half a day)

**In one sentence:** you book one PO on the test site by hand, exactly as the PO admin does, and Claude Code takes a snapshot of every screen along the way. Nothing is built yet: the agent's code (M1 onwards) is written from these snapshots.

The job has four parts, plus the screens off the happy path:

| Part | What you do in MySys | Rows |
|---|---|---|
| **1. Check the PO email** | Open the Note in the Agent Pool, assign it to the agent, download the PDF | 01–05 |
| **2. Create the task** | Find the project by its internal number, open it, click **Create New Task** | 06–08 |
| **3. Fill in the form** | Creator, Compaction Test, PO Number, PDF, Note → **Submit** → **Hold** | 09–12 |
| **4. Link and mark Solved** | Back on the Note: **Link to Project**, then **Solved** | 13–14 |
| **5. Off the happy path** | Send a Note back to the pool, search for a project that doesn't exist, a form error, a cancelled task | 15–18 |

**Why Claude needs this:** the agent finds every button by its role and name on the screen (for example, button "Solved"). Claude can't log in to MySys or click anything, so it learns each screen from your walkthrough: the buttons the agent will press, the defaults it must check, and the buttons it must never press (Discard, Unlink, Cancel, Unassign, Remove).

**Which PO gets what:**

| Trial PO | Project | What you do |
|---|---|---|
| **2609017B** | pln_66935 | Parts 1–4: a full booking (rows 01–14); then rows 16–18 |
| **2609034B** | pln_66938 | Look only: rows 02, 05, 06, 07 (open the Note, download the PDF, search, open the project), then row 15 (assign its Note to the agent and back to Agent Pool). No booking |
| **2610002B** | pln_66940 | Look only, same rows as 2609034B |

The two "look only" POs show Claude how Notes, PDFs and addresses vary. Booking them as well would add nothing and mean more resets.

No recording file is needed: Claude takes each screen's accessibility tree (every element's role and name, which boxes are ticked) and a screenshot itself, with Playwright CLI. Never use a video, a HAR file or saved cookies; they capture the password. Everything goes into `private/` (git-ignored, laptop only), because the test site may hold copies of real data.

### 3A. Test site: the walkthrough

**Before you start (once):**

1. Create the private folders:

   ```powershell
   mkdir private\captures\test, private\captures\live, private\pdfs, private\fixtures
   ```

2. Start `claude` in the repo and paste:

   ```text
   We're mapping the MySys test site for docs/workflow.md Stage 3A. Run: playwright-cli open --headed "https://test-prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component" — then wait. I log in and do every click and every typed value myself. You only observe. Don't run anything until I say "logged in". Then, each time I give you a row (e.g. "row 03, 2609017B"), run playwright-cli snapshot --filename=NN-<po>-<name>.yml and playwright-cli screenshot --filename=NN-<po>-<name>.png, and tell me in one or two lines what matters for the agent: defaults, ticked checkboxes, the controls it will need, and any Discard/Unlink/Cancel/Unassign/Remove buttons on the screen (use find or generate-locator on those, never click). Use no other playwright-cli command unless I ask.
   ```

   ✓ A Chromium window opens on the MySys login page. Approve the `open` command if Claude Code asks.

3. **Log in** as the **agent account** in that window. Claude never sees what you type. Then type `logged in` in Claude Code.

**How every row works:** do the step in the browser → type the row in Claude Code (e.g. `row 03, 2609017B`) → Claude saves a snapshot and a screenshot and tells you in a line or two what matters. Add anything a snapshot can't show (a wait, a pop-up, what changed after a click) as a sentence; ask Claude to keep `private/captures/test/notes.md`. If Claude asks to run any other `playwright-cli` command, say **no**.

**Part 1 — Check the PO email** (2609017B)

| Row | Do this | Look for |
|---|---|---|
| 01 | Project tab → Note Pool; open the **Assigned Pool** dropdown | The Locked filter; the 3 trial Notes (and any non-`/048` Note) |
| 02 | Open the 2609017B Note | Title, body, source, attachments |
| 03 | Click **Assign** and leave the dropdown open | ⚠ Is **Agent Pool** in the list? (check 3.2) |
| 04 | Assign it to the agent | Where the assignee shows |
| 05 | Download the PDF | What happens: new tab, file or prompt |

**Part 2 — Create the task**

| Row | Do this | Look for |
|---|---|---|
| 06 | **Projects** (not Tasks) → search `2609017B` | 1 result; where the internal number, company and address show (a made-up number is row 16) |
| 07 | Open the project (pln_66935) | How lot, street and suburb show; the task list and where PO numbers show |
| 08 | Click **Create New Task** (form still empty) | ⚠ **Send Email Notification**: ticked by default? (check 3.3); the Creator dropdown open; the task-type list |

**Part 3 — Fill in the form**

| Row | Do this | Look for |
|---|---|---|
| 09 | Fill in: Creator **Perth Scheduling**; tick **Compaction Test**; PO Number `2609017B/048`; upload the PDF; Note = the email body; **untick Send Email Notification**. Don't submit yet | Every field, just before Submit |
| 10 | **Submit** | Where the task type, PO number and document show |
| 11 | **Hold** → type `ON HOLD UNTIL CALL UP`; don't press the Hold button yet | ⚠ **Every related-task checkbox, and whether it's ticked** (check 3.1) |
| 12 | Press **Hold** | How "On Hold" and the hold note show |

**Part 4 — Link and mark Solved**

| Row | Do this | Look for |
|---|---|---|
| 13 | Back on the Note: **Link to Project** → search pln_66935 → select | The search, the result list, after selecting |
| 14 | **Solved** (the Note's Status buttons; there is no Resolve button) | How "Solved by" shows, the new log line, the Note gone from the Pending list; ⚠ does Send Email Notification appear here too? |

**Then the two "look only" POs:** rows 02, 05, 06 and 07 for 2609034B, then for 2610002B. Then Part 5.

**Part 5 — Off the happy path**

| Row | Do this | Look for |
|---|---|---|
| 15 | On the 2609034B Note: assign it to the agent, then pick **Agent Pool** in the pool dropdown → **Assign** | ⚠ Where the Note lands and how the assignee shows; the log line; that Unassign/Unlink weren't needed (check 3.2) |
| 16 | **Projects** → search a made-up number | **0 results**: the empty-list text; 2 results if you can find a case |
| 17 | *(Optional)* On pln_66935, **Create New Task** → tick Compaction Test → **Submit** with no PO document | The error message, and that no task was created |

**Reset, then finish:**

1. In your normal browser, logged in as **yourself** (the agent never cancels), **cancel** the Compaction Test task on pln_66935. Note whether an On Hold task can be cancelled directly or must be released first (check 3.6).
2. In the Playwright window, reload the pln_66935 page yourself and give Claude `row 18, 2609017B`, so the screen map shows how a cancelled task looks.
3. As B1 Homes, place a fresh copy of the 2609017B Note in the Agent Pool (Stage 6.1).
4. Ask Claude to run `playwright-cli close`.

✓ `private/captures/test/` holds a `.yml` and a `.png` for every row, plus `notes.md`; 2609017B is back in the Agent Pool with no live task on its project.

**Fallback if Node.js can't be used:** `uvx --from playwright playwright install chromium`, then `uvx --from playwright playwright codegen --target python -o private\captures\test\codegen-raw.py "<test-site URL>"`. Do the same rows, taking a screenshot (Win+Shift+S) of each into `private\captures\test\NN-<po>-<name>.png`. For buttons you must not click, use **Pick locator** in the Inspector and hover. Close the browser to save, then **delete the username and password lines** from `codegen-raw.py`.

### 3B. Live site: look only, with the agent's account

Real client data, so it stays in `private/`. **Change nothing on live:** no Assign, no edits, no bookings. First check on the test site that just opening a Note or downloading its PDF doesn't change it (check 3.5); if it does, capture live from the pool list only. Don't use Playwright CLI or the recorder on live; it's blocked in `.playwright/cli.config.json` too.

1. Log in to live in your normal browser. Screenshots to `private\captures\live\`: the PO Allocation Pool with the Locked filter; 3–4 real B1 Notes (title, body, attachments); one non-B1 or `/023` Note for contrast.
2. Save the **3 most recent real B1 `/048` PO PDFs** to `private\pdfs\` for the MVP. Before go-live, add more to reach 10–20 (mostly `/048`, a few other suffixes, and any odd ones you remember).
3. For each one, look up its project (view only) and fill one case in `private\fixtures\cases.toml`:

   ```toml
   [[case]]
   pdf = "2610123B_048_1.pdf"
   note_title = "[B1 Homes] Order 2610123B/048"
   note_body = "Please find attached Purchase Order / Quotation file 2610123B_048_1.pdf"
   lookup.project_matches = 1            # how many projects the internal number finds
   lookup.pln = "pln_00000"
   lookup.lot = "12"
   lookup.street = "Example Street"
   lookup.suburb = "Sampleville"
   lookup.existing_compaction_po = []    # PO numbers of Compaction Test tasks already on the project
   expect = "PROCEED"                    # or "SKIP" when a person would need to look at it
   expect_reason = ""                    # e.g. "ADDRESS_MISMATCH" when expect = "SKIP"
   ```

### 3C. The six checks (answer them during the walkthrough)

| # | Check | Where | If it goes the wrong way |
|---|---|---|---|
| 3.1 | **C1:** is any related-task checkbox in the Hold dialog ticked by default? | Row 11 | The agent can't safely put tasks on hold. CEO decision before M4 |
| 3.2 | **C3:** can a Note go back to the Agent Pool using **Assign** (not Unassign)? | Rows 03, 15 | Every skip would break a rule. CEO decision before M3 |
| 3.3 | Which screens show **Send Email Notification**? | Rows 08, 09, 14 | The agent must untick it everywhere |
| 3.4 | **MFA or password expiry** on the agent account? | Logging in | Unattended runs fail. Blocks M1 |
| 3.5 | Does opening a Note or downloading its PDF change anything? | Rows 02, 05 | Live capture (3B) is done from the pool list only |
| 3.6 | How does a **cancelled** task look? Can an **On Hold** task be cancelled directly? | Reset, row 18 | Changes the duplicate check and the reset steps |

### 3D. Turn it into the screen map

Before Claude Code reads real data: you're on a **Pro** plan, so turn off the model-training setting in your claude.ai privacy settings. Then start `claude`:

```text
Read everything in private/captures/ (snapshots, screenshots, notes.md, and codegen-raw.py if I used the fallback). Write docs/screen-map.md: one section per SOP screen in order, with each control's role and accessible name, what the agent must read back after each step, the defaults, and the differences between live and test. Use fake values only: no real names, addresses or PO numbers. Add dated entries to docs/decisions.md for checks 3.1–3.6. Don't copy any file from private/ into the repo. Done means: docs/screen-map.md covers rows 01–18 with fake values only, and docs/decisions.md has one dated entry per check 3.1–3.6.
```

Check the diff for real data and credentials. Don't copy test-site screenshots into `docs/screen-map/`: the 3 trial POs are real B1 POs (16 Oct 2026, `docs/decisions.md`), so test-site screenshots are real data. `/exit`, then commit on a branch and open a PR (Stage 5 steps 1, 8, 9).

✓ `docs/screen-map.md` merged; checks 3.1–3.6 have recorded answers; `private/` holds the captures, the real PDFs and `cases.toml`. If 3.1, 3.2 or 3.4 went the wrong way, stop and take it to the CEO first.

---

## Stage 4 — Define and plan (one session, about 1–2 hours)

**4.1 Check `SPEC.md` against the screen map.** The spec was approved on 15 Oct 2026 (v1.4). M0 may still change details (labels, C1, C3, how a cancelled task shows), so start `claude`:

```text
Read SPEC.md, CLAUDE.md, docs/screen-map.md, docs/specs/spec.md and docs/decisions.md. List anything in SPEC.md that the screen map contradicts, that is ambiguous, or that an engineer couldn't build from. Don't change files yet. Done means: a numbered list of issues, each naming the SPEC.md section and the screen-map evidence, or "none found".
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
     Done means: the task's acceptance criteria in tasks/plan.md are met and uv run scripts/check.py ends with "check: all passed". Stop at the test-first pause, as CLAUDE.md says.
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

**Set up the Mac Mini** and run the spike: follow `docs/macmini-setup.md` (section 2, the login by hand from the Mac Mini, first; then sections 3–9). ✓ SPEC criterion S1.

**If a screen turns out different later** (a selector fails in a test-site run): repeat Stage 3A for just that screen with Playwright CLI and ask Claude to update `docs/screen-map.md`.

### When to clear context

`/clear` (or `/exit`, then `claude`) gives Claude a fresh context. Nothing is lost: the plan and progress live in `tasks/plan.md` and `tasks/todo.md`, and decisions in `docs/`.

| Clear | Why |
|---|---|
| After each task's PR is open (steps 8–10) | One task per session (CLAUDE.md); the next task starts from the files, not the scrollback |
| After 3D (screen map written) | Claude read real captures and PDFs from `private/`; don't carry them into later sessions |
| Between 4.2 (plan) and 4.3 (doubt), and before the M4 booker challenge | `doubt-driven-development` only works from a context that didn't write the plan |
| After 4.4 (freeze), before the first build | The planning chat is long and no longer needed |
| The session is getting long, or two fixes in a row have failed | Ask for a handoff in the PR description first, then clear |

**Don't clear:** mid-task, including at the test-first pause (you approve, Claude carries on with the test in mind); during a `/build auto` run; or while a debugging session is still making progress. If Claude Code starts summarising older turns on its own, finish the current task and clear at the next task boundary.

### When something goes sideways

- Remembered something mid-run: type it and press Enter while Claude works (e.g. "Also read back the Creator field"). Don't stop and restart; runs are long.
- Session getting long: ask Claude to write a short handoff (what's done, what's next, open problems) into the PR description, `/exit`, start again.
- A Mac Mini run failed: read `~/Library/Logs/po-agent/runs.log` (and `launchd.log`) first; a loaded job doesn't mean the run worked.

---

## Stage 6 — Verify on the test site

**6.1 Reset the test site** (after the walkthrough, before M3, after every booking test, and before the M6 demo), with **your own account**, by hand. The agent never cancels anything.

- [ ] On pln_66935, pln_66938 and pln_66940: **cancel** every non-cancelled Compaction Test task with the trial PO numbers (2609017B/048, 2609034B/048, 2610002B/048).
- [ ] The 3 trial Notes (2609017B, 2609034B, 2610002B) are in the **Agent Pool**, unassigned, with their PDFs. Place fresh copies if earlier ones were Solved.
- [ ] Nothing is left assigned to the agent account.

**6.2 Seam 2 from the laptop:** `uv run pytest tests/seam2 -m testsite` (Claude may run it if you ask). ✓ All cases pass; reset again afterwards.

**6.3 On the Mac Mini:** as `poagent`, `~/po-agent/scripts/macmini-run.sh decide-only` (M3), then `launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent` (M4, one PO). ✓ `runs.log` ends with `RUN_SUMMARY` and `"exit_code": 0`.

---

## Stage 7 — MVP demo (M6)

1. **Go/no-go checklist:** in Claude Code, `/ship` — `Prepare the go/no-go for the MVP demo on the test site: checklist against SPEC.md S1–S8, the rollback (launchctl bootout; enabled = false), and what to watch in the first run.` You decide go or no-go.
2. **Rehearse stopping:** set `enabled = false` in `config/test.toml` (PR, merge), start a run with `launchctl kickstart` and check it exits before login; set it back to `true`. Check `launchctl bootout` stops the job, then bootstrap it again.
3. **Reset** the test site (6.1). As B1 Homes, place the 3 trial Notes in the Agent Pool. Only the 3 trial POs are used; leave any non-`/048` Note that's already in the pool where it is.
4. **Load the launchd job** (`docs/macmini-setup.md` section 8). Don't touch anything until the next run has finished.
5. Check every pln and Note against `SPEC.md` S4. Then place **a fresh copy of the 2609034B Note** in the Agent Pool and let the next run happen: it must skip it as `DUPLICATE_TASK`, return it to the Agent Pool and change nothing else (S5). Check the controls work (S6).
6. **Repeat it (S8):** do the reset in `docs/demo-runbook.md` and run the demo again, at least 3 times in a row, without changing code or config. Try the laptop way (`--headed --slow-mo 500`) once, so you know which to use in front of your boss.
7. Total the cost per PO from the `NOTE` and `RUN_SUMMARY` lines in `runs.log` (S7), add the real-PO seam result (S3), and write a one-page MVP demo note for the CEO: what ran, where (the office Mac Mini), the trial conditions, cost per PO, open concerns.

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
4. **Production on the Mac Mini** (roadmap phase 4; CEO decision 3 made): live credentials into `poagent`'s Keychain after the go-live sign-off, `/ship` plus `engineering:deploy-checklist` in Cowork.

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
| `protect_paths.py` | **Blocks** edits to `.claude/**`, `config/live*.toml`, `.env*`, `secrets/**`, `state/**` and paths outside the repo. **Asks** before edits to `.github/workflows/**`, `docs/macmini-setup.md`, `scripts/macmini-run.sh`, and existing files in `tests/seam1/fixtures/**` or expected results. |
| `guard_bash.py` | **Blocks** commands mentioning the live site (regex `(?<!test-)prompt\.mysys\.com\.au`); any `playwright-cli` command except `open` (test URL only, no `--persistent`/`--profile`), `snapshot`, `screenshot`, `find`, `generate-locator`, `tab-list`, `list`, `close`; `printenv`, a bare `env`, `/proc/*/environ`, or any text containing `PO_AGENT_`; `git push --force`; any push to `main`; `gh pr merge`; `rm -rf`; `git add`/`commit` of `private/`, `state/`, `logs/`, `.env*`; text matching a real Anthropic key (regex `sk-ant-[A-Za-z0-9_-]{20,}`). |
| `format_python.py` | For `.py` files: `ruff format` then `ruff check --fix` on that file; reports leftover lint errors. |
| pre-commit + gitleaks | Secret scan on every commit, including Joey's own; also blocks any staged path under `private/` and any `.pdf` outside `tests/seam1/fixtures/pdfs/`. The same path rule runs in `scripts/check.py`, so CI catches it too. |

Rules for all hooks: read the tool call as JSON on stdin; exit 2 to block, with stderr saying what was blocked, why, and that Joey does it by hand; to ask, print `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": "..."}}` and exit 0; keep them fast.

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
| A Mac Mini run waits forever | A Keychain "allow access" dialog after a Python change: log in as `poagent` at the Mac, run the spike, click **Always Allow** (`docs/macmini-setup.md` section 7). |
| No runs after a power cut or restart | The Mac is waiting at the FileVault screen: log in as `poagent` and lock the screen (`docs/macmini-setup.md` section 10). |
| The Mac Mini can't log in to MySys | Check the spike output and try a login by hand in Safari on the Mac Mini; if MySys blocks the office address, record it in `docs/decisions.md` and tell the CEO. |

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
- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)

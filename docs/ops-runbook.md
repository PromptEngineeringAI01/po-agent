# Ops runbook - PO Agent on the Mac Mini (live and test site)

**Version:** 1 · 9 Nov 2026 · **Owner:** Joey Wu · **For:** the backup admin (go-live gate 4) and Joey · **Spec:** `SPEC.md` → Commands (exit codes), Code style (run output), Production (Safe trace); `docs/macmini-setup.md` sections 8-11

What to do when the agent raises an alert. Written so the backup admin can follow it without Joey. From go-live the Mac Mini runs **live MySys** only (`run live`; decisions, 10 Nov 2026, live profile). The steps are the same on both sites; where the sites differ, both are named.

The agent runs on the office Mac Mini as the macOS user `poagent`, every weekday at 7 minutes past each hour, 07:07 to 17:07 Perth time. Each run books B1 Homes compaction POs from the agent's pool (**PO Allocation Pool** on live, Agent Pool on test): a Compaction Test task on the project with the PO PDF attached, put On Hold, then the Note linked to the project and Solved. When it is unsure, it hands the Note back to that pool and changes nothing. When something goes wrong, it stops and raises an alert.

**Never, while following this runbook:**
- Type or paste a password, token or other secret into a chat, an issue, a file or a message. Type it only into the prompt or field that asks for it.
- Put an address, a client name or text from a PDF into a GitHub issue or comment. The repository is public. Nor a **live** Note ID or pln: those are real client data. A run_id and a step are fine (on the test site a Note ID and pln are too).
- Leave **Send Email Notification** ticked when you change a Note in MySys by hand. Untick it before every Assign, Link to Project and Solved.
- Edit files in `~/po-agent` on the Mac Mini, or move the `production` tag (only Joey moves it).
- Run the agent from a laptop while the Mac Mini job is loaded (one agent at a time).

## 1. Before you need this (once)

- [ ] An admin account on the Mac Mini, and the `poagent` macOS password from the company password manager.
- [ ] Your own MySys login on the site the agent runs on (live after go-live), to fix bookings by hand. Use your own account for that, not the agent's, so the Note's log shows who did it.
- [ ] Alert emails: GitHub emails Joey about each alert. To get them too, sign in to GitHub, open the `PromptEngineeringAI01/po-agent` repository, click **Watch** → **Custom** → tick **Issues** → **Apply**.
- [ ] Read section 3 once, so you know the common tasks before an alert arrives.

## 2. How an alert reaches you

Every alert is a GitHub issue labelled `po-agent-alert`, and GitHub sends an email about it. There are three kinds of title:

| Issue title | Opened by | Body |
|---|---|---|
| `po-agent alert <run_id>` | The Mac Mini, after a run that printed an `ALERT` line or exited non-zero | The `ALERT` lines without Note IDs, sometimes a `wrapper:` line, and `exit code: <n>` |
| `po-agent alert no run_id` | The Mac Mini, when the agent didn't start or printed no summary | A `wrapper:` line and `exit code: <n>` |
| `po-agent heartbeat missed` | GitHub itself (`.github/workflows/heartbeat.yml`) | No run has finished for more than 2 hours inside the schedule |

An `ALERT` line looks like this (placeholders in `<>`):

```text
ALERT PARTIAL_WRITE {"note_id": "<note_id>", "step": "W3", "detail": "task not held (step=W3, note_id=<note_id>)"}
```

- The word after `ALERT` is the kind: find its entry in section 4.
- `note_id` is the MySys Note the agent was working on (empty when it had none). **The issue body leaves it out** (the `note_id` key and the detail's `note_id=...`; audit N4): the Note is named only on the Mac Mini: as `poagent`, `grep <run_id> ~/Library/Logs/po-agent/trace/<YYYY-MM-DD>.jsonl` gives that run's Note IDs and steps, and in `runs.log` the run's whole `ALERT` lines sit just above its `RUN_SUMMARY` with that `run_id`.
- `step` says how far it got. `W1` fills the Create New Task form; `W2` is the **Submit** click and its checks; `W3` is Hold; `W4` is Link to Project; `W5` is Solved. **From W2 on, the task may exist in MySys.**
- `detail` is a fixed sentence from the code, never page text.

**Exit codes:** 0 run finished (bookings and skips are normal) · 1 run stopped (unexpected screen, Note Pool more pages, failed write, partial write, guard refusal, or killed at the time limit) · 2 config, secrets, login or wrapper setup problem · 3 accuracy breach.

**First steps for any alert:**

1. Read the issue body. Find each `ALERT` kind or `wrapper:` line in section 4.
2. If you need more, on the Mac Mini as `poagent`, in Terminal: `tail -50 ~/Library/Logs/po-agent/runs.log`. Each run starts with a line `=== <time> macmini-run.sh <mode> <site> ===` and ends with `RUN_SUMMARY {...}`.
3. For the agent's steps in that run: `grep <run_id> ~/Library/Logs/po-agent/trace/<YYYY-MM-DD>.jsonl` (the Perth date of the run). It holds only Note IDs, steps, check names, outcomes and times.
4. Do what the entry says. Leave the alert issue open for Joey's triage (plan task 7.6), and add a comment saying what you did, using only the run_id and steps (on the test site Note IDs and plns too). The one exception: close `po-agent heartbeat missed` yourself once runs are back.

## 3. Common tasks

### 3.1 Stop the agent

Either one stops the next run. After an `ACCURACY_BREACH`, do both.

1. **Unload the job** (you can do this without Joey). On the Mac as `poagent`, in Terminal:
   ```bash
   launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent
   ```
   Or as an admin (at the Mac or over Remote Login):
   ```bash
   sudo launchctl bootout gui/$(id -u poagent)/au.com.prompteng.po-agent
   ```
   Check: `launchctl print gui/$(id -u)/au.com.prompteng.po-agent` (as `poagent`) now says it can't find the service. If a run was going (from :07, for up to 20 minutes), it is stopped too and may leave a Note with the agent: check for one (3.3) before you restart. Between about :30 and :05 no run is going.
2. **The kill switch** (Joey): `enabled = false` in the site's config on `main` (`config/live.toml` after go-live, `config/test.toml` for test runs), through a pull request. The next run reads it from `main` whatever commit the `production` tag is on, logs `wrapper: enabled = false on main, agent not run`, runs nothing, opens no alert and exits 0.

While the job is unloaded, the heartbeat check will open `po-agent heartbeat missed` after 2 hours inside the schedule. That is expected: leave it open until runs are back.

### 3.2 Restart the agent

1. Fix the cause first (the alert's entry in section 4), and make sure no Pending Note is still assigned to the agent (3.3), or the next run stops at the start.
2. If code or the site's config had to change: Joey merges the fix to `main`, tries it on the test site from the laptop (job unloaded) and moves the `production` tag to it (`docs/macmini-setup.md` section 8). Nobody else moves the tag. If Joey set `enabled = false`, he sets it back to `true` on `main`. The agent also reads `enabled` from the tagged commit's config, so the tag must be on a commit whose config says `true`: if the tag was moved while `main` said `false`, Joey moves it again after setting `true`.
3. As `poagent` on the Mac, try a read-only run first. It logs in and lists the Notes, and takes none. Don't start it within a few minutes of :07.
   ```bash
   ~/po-agent/scripts/macmini-run.sh spike live
   tail -20 ~/Library/Logs/po-agent/runs.log
   ```
   Healthy: `wrapper: running production <commit>`, `INFO  logged in`, and a last line `RUN_SUMMARY {...}` with `"exit_code": 0`.
4. If you unloaded the job, load it again, as `poagent`:
   ```bash
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/au.com.prompteng.po-agent.plist
   launchctl print gui/$(id -u)/au.com.prompteng.po-agent | head -30
   ```
5. Wait for the next scheduled run, or start one now (this one books):
   ```bash
   launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent
   ```
6. Check its `RUN_SUMMARY` in `runs.log`. Lock the screen when you leave (Control-Command-Q); don't log `poagent` out.

### 3.3 Find a Note and its project in MySys

Log in to MySys (live after go-live, else the test site) with your own account. Get the `<note_id>` from the Mac Mini (section 2): the alert issue doesn't carry it.

1. **Note Pool:** Assigned Pool = **All Pools**, Assigned User = **All Users**, Locked/Unlocked = **All**; type `<note_id>` in Search/filter, then press **Refresh**. Use the row whose ID is exactly `<note_id>` (the search also matches longer IDs). The Status filter decides which Notes show: Pending lists only Notes not yet Solved.
2. The row shows the Note's Assignee and Status. **Still with the agent** means Assignee "Agent 1 (MySys Only)" and Status Pending.
3. Open the Note. Its attachment is named `<internal no>_048.pdf` (sometimes with `_1` before `.pdf`); the PO number is `<internal no>/048`.
4. **Project:** Project → Projects, search `<internal no>`, and open the row with Company **B1 Homes** and Client Ref No. exactly `<internal no>`. Its `pln_...` is the `<pln>`.
5. On the project's **Tasks** tab, look for Compaction Test tasks that aren't Cancelled. A task the agent made has Lodged By "Agent 1 (MySys Only)".

### 3.4 Return a Note to the agent's pool by hand

Only for a Note the agent took but where **no task was created** for it (no new non-Cancelled Compaction Test task on its project).

1. Open the Note (3.3).
2. Untick **Send Email Notification**.
3. User list: `--Select User--`. Pool list: **PO Allocation Pool** on live (**Agent Pool** on test). Press **Assign** once.
4. Check: Assignee reads that pool, Status Pending.

The next run picks it up again. Never use Unassign or Unlink.

### 3.5 Finish a booking by hand

For a Note the agent left after the **Submit** click (step W2 to W5). The goal is what the agent would have done. Do only the parts that aren't done yet, with your own account.

1. Open the project `<pln>` (3.3), Tasks tab. Count the non-Cancelled Compaction Test tasks made for this PO:
   - **None:** the Submit didn't create one. Return the Note (3.4) and stop here.
   - **More than one:** keep one (the one with every value right) and **Cancel** the others.
   - **One:** go on.
2. **Check the task** (open it from its details row): PO Number `<internal no>/048`; Task Creator **Perth Scheduling**; **- Compaction Test** the only service ticked; Notes = the Note's body text; and on the project's **Documents** tab, under that task, one row with the Note's PDF, Type **Purchase Order** (on both sites). Fix a wrong value by hand. If you can't, Cancel the task and book it by hand (3.6).
3. **Hold** (if its Status doesn't start "On-hold"): press **Hold** on that task's row. In the "Hold Task: `<task no>`" window, type `ON HOLD UNTIL CALL UP` in Note. Check that no related job is ticked (only this task is held), then press that window's **Hold**. The Status now starts "On-hold" and shows the note.
4. **Link** (if the Note has no project button showing `<pln>`): open the Note, untick **Send Email Notification**, press **Link to Project**, search `<pln>` and select it. If the Note is linked to a **different** project, use Change Project to put it on `<pln>`.
5. **Solved** (if the Note isn't Solved): untick **Send Email Notification**, then Status → **Solved**.
6. Leave the Note assigned to the agent. Once it is Solved, runs no longer stop on it.

### 3.6 Book a PO by hand

Only when a task had to be cancelled in 3.5. On project `<pln>`: **Create New Task**. Creator (Client section) = **Perth Scheduling**; tick **- Compaction Test**; PO Number = `<internal no>/048`; upload the Note's PDF to **PO Documents** (not the separate Documents upload); Note = the Note's body text; leave everything else as it is; **Submit**. Then 3.5 steps 3 to 6.

### 3.7 Change the MySys password in the Keychain

When the agent account's password has changed (or was reset). The live account's items are `mysys_live_password` and `mysys_live_username`; the test site's `mysys_test_password` and `mysys_test_username`:

1. Get the new password from whoever changed it (the MySys admin) or the company password manager. Keep it there; don't send it anywhere.
2. Log in at the Mac as `poagent`. In Terminal:
   ```bash
   cd ~/po-agent
   uv run keyring set po-agent mysys_live_password
   ```
   It asks for the password: type it (nothing shows) and press Return.
3. Run one spike: `~/po-agent/scripts/macmini-run.sh spike live` (not within a few minutes of :07).
4. If macOS asks whether Python may use the "po-agent" item in your keychain, type the `poagent` macOS password and choose **Always Allow**. If it asks again (once per item), choose **Always Allow** again. A run left waiting on this dialog is killed after 20 minutes and alerts.
5. Check `runs.log`: `INFO  logged in` and `"exit_code": 0` in the last `RUN_SUMMARY`.
6. Lock the screen (Control-Command-Q).

The username works the same way with `mysys_live_username`. For the test site, use the `mysys_test_` names and `spike test`.

### 3.8 Who is told

- **Joey:** GitHub emails him about every alert issue, automatically.
- **The backup admin:** gets the same email by watching the repository's issues (section 1). Acts when Joey is away, and comments on the issue so Joey knows what was done.
- **The CEO:** only after an `ACCURACY_BREACH`. The agent restarts only with the CEO's agreement.
- On the test site no client is affected and the PO admin isn't involved, so nobody else needs telling. On live, who else is told is Joey's call (not decided yet).

## 4. The alerts

### PARTIAL_WRITE (exit 1)

- **Means:** the agent pressed Submit (step W2 or later) and then couldn't finish or confirm the rest, so the booking may be half done. Ctrl+C or the kill switch in that stretch also gives `PARTIAL_WRITE`. The Note is **left assigned to the agent** on purpose. Until a person finishes it, every later run stops at the start with `UNEXPECTED_SCREEN` "a Note is still assigned to the agent from an earlier run" and takes no Note.
- **In MySys:** finish it by hand (3.5), using the alert's `step` and its `note_id` from the Mac Mini (section 2).
- **Restart:** none needed if the job is still loaded: once the Note is Solved (or returned, when no task was made), the next run goes on. If the same `PARTIAL_WRITE` comes back, stop the agent (3.1) and leave it for Joey.
- **Told:** Joey (automatic). Comment on the issue with what you finished.

### ACCURACY_BREACH and the STOP file (exit 3)

- **Means:** the agent read back something it wrote and it was wrong (step W2 to W5): for example a value on the new task or its document, or the Note linked to another project. This is the most serious alert. The Note is **left assigned to the agent**, so every later run stops at the start until a person deals with it.
- **The STOP file:** the full design has the agent write a `STOP` file after a breach. That isn't built: there is no `STOP` file. Its place is taken by the Note left with the agent, plus the two stops in 3.1, done by people.
- **First:** stop the agent: unload the job yourself (3.1 step 1) and ask Joey to set `enabled = false` on `main` (3.1 step 2).
- **In MySys:** fix the wrong value by hand, then finish the booking (3.5). If the Note is linked to the wrong project, put it on the right `<pln>` (Change Project) before Solved.
- **Restart:** only with the **CEO's agreement**, after Joey has found and fixed the cause. Then Joey sets `enabled = true` on `main` and moves the `production` tag if the code changed, and you or Joey restart (3.2).
- **Told:** Joey (automatic) and the CEO (Joey, or you if Joey is away).

### GUARD_REFUSAL (exit 1)

- **Means:** the agent's safety guard blocked a click it was about to make (a forbidden or unknown button, or one that matched twice). Nothing was pressed by that action.
- **In MySys:** look at `step`. **No step, or W1:** nothing was submitted. The Note was handed back to the pool; if it's still with the agent, return it (3.4). **W2 to W5:** the Note is left with the agent; treat it as a `PARTIAL_WRITE` and finish it by hand (3.5).
- **Restart:** a refusal usually means a MySys screen changed or a bug. Stop the agent (3.1) if it happens twice, and leave the cause to Joey.
- **Told:** Joey (automatic).

### UNEXPECTED_SCREEN (exit 1), also the silent-skip signal

- **Means:** MySys didn't look as expected, or an unexpected error happened. The run stops on the **first** one, so a MySys screen change can't make every Note skip quietly: this alert is the signal for that (there is no separate "all skipped" alert). Business skips such as `NOT_B1` or `DUPLICATE_TASK` never alert. Check the `detail`:
  - **"a Note is still assigned to the agent from an earlier run"** (with a `note_id`): an earlier run left that Note half done, or couldn't hand it back. No Note was taken this run. Find that `note_id` on the Mac Mini (section 2) and look at the earlier alert for it. Then in MySys (3.3): if no task was made for it, return it (3.4); if one was, finish it (3.5). Runs go on by themselves once the Note isn't Pending with the agent.
  - **"run stopped; Note not returned to the pool"**: the agent stopped before Submit and couldn't hand the Note back. Return it by hand (3.4).
  - **Anything else** (for example "unexpected error (type=...)", "Note not found once"): nothing was submitted and the Note was handed back. Nothing to undo. If the alert has step W2 to W5, treat it as `PARTIAL_WRITE` (3.5).
- **Restart:** the next run tries again by itself. If the same alert comes **two runs in a row**, POs aren't being booked: stop the agent (3.1) and tell Joey that a MySys screen may have changed.
- **Told:** Joey (automatic).

### MORE_PAGES (exit 1)

- **Means:** the Note Pool's list has a second page, which the agent never reads, so it stopped before taking any Note. The detail is "Note Pool has more pages: stale-Note read incomplete" (test: the check of all Pending Notes, any pool or user), "My Notes has more pages: stale-Note read incomplete" (live: the agent's own My Notes tab, so the agent holds more Pending Notes than fit on one page) or "Note Pool has more pages: page 2 not read" (the PO Allocation Pool + Locked list is over one page, 50). On live a My Notes row already stops the run as `UNEXPECTED_SCREEN`, so the My Notes detail is rare.
- **In MySys:** nothing to undo. The count of Pending Notes has to come down below one page. Which Notes to deal with first is Joey's call.
- **Restart:** every run stops with this alert until the count is down; then the next run goes on by itself. If it will take more than a day, stop the agent (3.1) to save the hourly alerts.
- **Told:** Joey (automatic).

### LOGIN_FAILED (exit 2)

- **Means:** "login did not reach the app": the agent couldn't log in to MySys (live after go-live). Usual causes: the agent account's password changed or expired, the account is locked, or MySys or the office internet is down.
- **Check:** on the Mac Mini, open Safari, go to the site the agent runs on and log in by hand with the agent account (`docs/macmini-setup.md` section 2). Then log out and quit Safari.
  - **Password rejected:** get the new password from the MySys admin and put it in the Keychain (3.7).
  - **Account locked:** ask the MySys admin to unlock it.
  - **Site or internet down:** wait. Each hourly run tries again.
- **In MySys:** if the run's `ALERT` line in `runs.log` has a `note_id`, check that Note (3.3): if it's still with the agent and no task was made, return it (3.4).
- **Restart:** after the fix, run one spike (3.7 step 3). Scheduled runs then go on by themselves.
- **Told:** Joey (automatic). Tell the MySys admin if the account was locked.

### CONFIG (exit 2)

- **Means:** a setting or secret is missing or wrong, so the run stopped before opening a browser. Nothing in MySys changed. Check the `detail`:
  - **"secret not set (env var or keyring)"** (with `secret=<name>`): that item is missing from `poagent`'s Keychain. Add it (3.7, with that name).
  - **"secret store unavailable"**: the Keychain couldn't be read, usually because it is locked. Log in at the Mac as `poagent`, run one spike (3.7 steps 3 to 6), and lock the screen.
  - **"leftover download folder not removed"**: a temp folder from an earlier run couldn't be deleted. As `poagent`: `ls -d "$TMPDIR"po-agent-dl-* /tmp/po-agent-dl-*` shows them; `rm -rf "$TMPDIR"po-agent-dl-* /tmp/po-agent-dl-*` deletes them. It may hold a PO PDF, so delete it, don't copy it. If that fails too, restart the Mac (`docs/macmini-setup.md` section 10).
  - **"config file not readable"**, **"config file is not valid TOML"**, **"invalid config value"**, **"unknown site"**, **"config file is for another site"**, **"unknown time zone"** or **"invalid command line"**: the code or the site's config (`config/live.toml` or `config/test.toml`) at the `production` tag is wrong. Joey fixes it on `main` and moves the tag.
- **Restart:** after a Keychain or folder fix, run one spike (3.2 step 3); scheduled runs then go on. For a config fix, Joey restarts (3.2 step 2).
- **Told:** Joey (automatic).

### 7.2's alert: no separate alert

Plan task 7.2 planned an "every Note skipped" alert (`ALL_SKIPPED`). It was never added, because it could never fire (decisions, 5 Nov 2026): the run already stops on its first `UNEXPECTED_SCREEN`, and a second page of Notes is `MORE_PAGES`. Use those two entries.

### Missed heartbeat (`po-agent heartbeat missed`)

- **Means:** no run has finished for more than 2 hours inside the schedule (07:07 to 17:30 Perth, weekdays). Every run, even a failed one, updates the issue labelled `po-agent-heartbeat`, so this means runs aren't happening or can't reach GitHub. Nothing alerts at night, at weekends or in the first 2 hours of a day.
- **Check, in this order:**
  1. **Did someone unload the job on purpose** (after an earlier alert)? Then this is expected: leave it open until runs are back.
  2. **At the Mac:** if it shows the FileVault unlock screen (after a power cut or restart), unlock it with the **`poagent`** account, then lock the screen (Control-Command-Q). If it is off, turn it on and do the same.
  3. **As `poagent`:** `launchctl print gui/$(id -u)/au.com.prompteng.po-agent | head -30`. If it can't find the service and nobody unloaded it on purpose, load it (3.2 step 4).
  4. `tail -50 ~/Library/Logs/po-agent/runs.log`: if recent runs are there with `wrapper: heartbeat not sent`, runs work but GitHub can't be reached: check the internet, and whether the Mac Mini's GitHub token has expired (it lasts 90 days; see the setup failure for `git fetch` below).
  5. A dialog on `poagent`'s screen asking for Keychain access: choose **Always Allow** (3.7 step 4).
- **In MySys:** nothing to undo. Notes wait in the pool until runs are back.
- **Restart:** once a run has finished (`RUN_SUMMARY` in `runs.log`), **close** the `po-agent heartbeat missed` issue (or ask Joey to, if your GitHub account can't). Another one opens if runs stop again.
- **Told:** Joey (automatic; GitHub emails him about this issue directly).

### Wrapper setup failed (exit 2)

The issue (`po-agent alert no run_id`) holds `wrapper: setup failed (<step>), agent not run` and `exit code: 2`. The Mac Mini fetches the code and checks the switch before each run; when that fails, the agent doesn't run at all and never falls back to older code on disk. Nothing in MySys changed. For more, as `poagent`: `tail -50 ~/Library/Logs/po-agent/launchd.log`.

| `<step>` | Means | Fix |
|---|---|---|
| `git fetch` | The Mac Mini couldn't reach GitHub: internet down, or its GitHub token expired | Internet: wait, the next run tries again. Token: as `poagent`, `cd ~/po-agent && git fetch origin` shows an authentication error. Joey makes a new token (`docs/macmini-setup.md` section 1), then as `poagent`: `gh auth login --hostname github.com --git-protocol https --with-token`, type it, then Control-D. An expired token also stops alert issues and the heartbeat, so this one often arrives as a missed heartbeat |
| `enabled on main` | The site's config (`config/live.toml` or `config/test.toml`) on `main` doesn't have exactly one `enabled = true` or `enabled = false` line | Joey fixes `main` |
| `production tag missing` | There is no `production` tag | Joey creates it (`docs/macmini-setup.md` section 8). Nobody else |
| `git checkout` | The tagged code couldn't be checked out, usually because a file in `~/po-agent` was edited by hand | As `poagent`: `cd ~/po-agent && git status`. For each file it lists as modified: `git restore <file>` (this throws away the hand edit; nobody should edit files there). Then run one spike (3.2 step 3) |
| `uv sync` or `playwright install` | Installing the agent's packages or browser failed: internet down or disk full | Check the internet and free disk space; the next run tries again |

**Restart:** none needed: each scheduled run tries the setup again. Check the next run's `wrapper: running production <commit>` line.
**Told:** Joey (automatic). The tag and `main` fixes are his.

### Other `wrapper:` lines

- **`wrapper: agent killed at the 1200s limit`** (exit 1, in the alert issue): the run took over 20 minutes and was stopped. Usual causes: a Keychain dialog waiting for a click (3.7 step 4) or MySys very slow. A Note it was working on may be left with the agent: the next run then stops with `UNEXPECTED_SCREEN` "a Note is still assigned to the agent from an earlier run"; follow that entry.
- **`wrapper: alert issue not opened`** (in `runs.log` only): GitHub couldn't be reached, so an alert wasn't raised. Read the `ALERT` lines just above it in `runs.log` and act on them as if the issue had opened. Then check the internet and the GitHub token (`git fetch` above).
- **`wrapper: heartbeat not sent`** (in `runs.log` only): the run's ping didn't reach GitHub. Two hours of this inside the schedule opens `po-agent heartbeat missed`.
- **`wrapper: enabled = false on main, agent not run`**: not an alert. The kill switch is on; runs start again when Joey sets it back to `true`.
- **`wrapper: leftover Playwright browser killed`**: not an alert. Housekeeping after a run.

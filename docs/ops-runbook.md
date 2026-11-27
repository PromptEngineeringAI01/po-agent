# Ops runbook - PO Agent on the Mac Mini (live and test site)

**Version:** 1.2 · 27 Nov 2026 (1.2: Summit live since 27 Nov 2026 at one Note per run; which Notes the 07:30 run may take from a colleague; nobody assigns a Note to Agent 2 by hand; decisions, 27 Nov 2026, Summit go-live waiver. 1.1: Summit Home's run beside B1's, task 9.15: its job, alerts, Healthchecks check, Agent 2's Keychain items, giving a Summit Note back by hand, stopping Summit alone; decisions, 26 Nov 2026, Summit on the Mac Mini) · **Owner:** Joey Wu · **For:** the backup admin (go-live gate 4) and Joey · **Spec:** `SPEC.md` → Commands (exit codes), Code style (run output), Production (Safe trace); `docs/macmini-setup.md` sections 8-11

What to do when the agent raises an alert. Written so the backup admin can follow it without Joey. From go-live the Mac Mini runs **live MySys** only (`run live`; decisions, 10 Nov 2026, live profile). The steps are the same on both sites; where the sites differ, both are named.

The agent runs on the office Mac Mini as the macOS user `poagent`, every weekday at 7 minutes past each hour, 07:07 to 17:07 Perth time. Each run books B1 Homes compaction POs from the agent's pool (**PO Allocation Pool** on live, Agent Pool on test): a Compaction Test task on the project with the PO PDF attached, put On Hold, then the Note linked to the project and Solved. When it is unsure, it hands the Note back to that pool and changes nothing. When something goes wrong, it stops and raises an alert.

**Summit Home** (client 2, from go-live step S.5; `SPEC.md` -> Client 2) runs beside it as a separate run: its own launchd job `au.com.prompteng.po-agent.summit` at **30 minutes past** each hour, 07:30 to 17:30 Perth, weekdays, logged in to live MySys as **Agent 2 (Summit Homes)**. It reads the Note Pool at Source `support@prompteng.com.au` + Unlocked, opens a Note only to read it, takes it only when every check passed, books it like B1 (Creator from the creator table in `config/clients/summit.toml`), and gives a Note it can't finish back to whoever had it (its original assignee). B1's runs and alerts are unchanged. Where Summit differs, the entry says **Summit**. Both runs write to the same `runs.log`; a Summit run's first line ends `... live summit ===` and its `RUN_SUMMARY` has `"client": "summit"`. Live since 27 Nov 2026, one Note per run (`max_notes_per_run = 1`) until Joey has checked its first booking (decisions, 27 Nov 2026, Summit go-live waiver).

**Which Summit Notes Agent 2 takes:** every run after 08:00 Perth takes only a Note with no assignee (`---`). The 07:30 run (the first of the day, before 08:00) may also take a Note a colleague holds, to catch one picked up overnight, but only one it will book: a compaction-test PO that passed every check. Any other Note it only reads (opened read-only, nothing changed, no log line) and never takes, so it stays with whoever had it. Nobody assigns a Note to Agent 2 by hand: Agent 2 would hold it and every later Summit run would stop at the start until it is given back (3.4a).

**One run at a time by hand:** before starting any run by hand, as `poagent`: `pgrep -fl macmini-run.sh` must print nothing (no run going). Both jobs use the same checkout `~/po-agent`, and the schedule (:07 and :30, each agent run stopped at 20 minutes) usually keeps them apart; a slow setup (a Chromium download after a Playwright update) can make a B1 run still be going at :30. That is safe unless the `production` tag moved in between, so Joey moves the tag only when no run is going.

**Never, while following this runbook:**
- Type or paste a password, token or other secret into a chat, an issue, a file or a message. Type it only into the prompt or field that asks for it.
- Put an address, a client name or text from a PDF into a GitHub issue or comment. The repository is public. Nor a **live** Note ID or pln: those are real client data. A run_id and a step are fine (on the test site a Note ID and pln are too).
- Leave **Send Email Notification** ticked when you change a Note in MySys by hand. Untick it before every Assign, Link to Project and Solved.
- Assign a Note to **Agent 2 (Summit Homes)** by hand (Summit runs then stop at the start; above).
- Edit files in `~/po-agent` on the Mac Mini, or move the `production` tag (only Joey moves it).
- Run the agent from a laptop against the live site (only the Mac Mini runs on live). A laptop test-site run doesn't need the job unloaded.

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
| `po-agent alert summit <run_id>` or `po-agent alert summit no run_id` | The Mac Mini, after a **Summit** run, as the two rows above | The same |
| `po-agent heartbeat missed` | GitHub itself (`.github/workflows/heartbeat.yml`) | No run has finished for more than 2 hours inside the schedule. Checked about once each weekday afternoon, so it can arrive hours after runs stopped. A backup since 19 Nov 2026 |

**One alert is an email, not an issue:** Healthchecks.io emails Joey when the check `po-agent b1-homes` goes **down**: no run has ended within 40 minutes of a scheduled :07 (decisions, 19 Nov 2026). It comes within about an hour of a stop; see "Healthchecks.io down" in section 4. It emails again when the check is **up**. **Summit** has its own check, `po-agent summit` (within 40 minutes of a scheduled :30). The GitHub `po-agent heartbeat missed` issue is about B1's runs only: Summit runs don't update the heartbeat issue.

An `ALERT` line looks like this (placeholders in `<>`):

```text
ALERT PARTIAL_WRITE {"note_id": "<note_id>", "step": "W3", "detail": "task not held (step=W3, note_id=<note_id>)"}
```

- The word after `ALERT` is the kind: find its entry in section 4.
- `note_id` is the MySys Note the agent was working on (empty when it had none). **The issue body leaves it out** (the `note_id` key and the detail's `note_id=...`; audit N4): the Note is named only on the Mac Mini: as `poagent`, `grep <run_id> ~/Library/Logs/po-agent/trace/<YYYY-MM-DD>.jsonl` gives that run's Note IDs and steps, and in `runs.log` the run's whole `ALERT` lines sit just above its `RUN_SUMMARY` with that `run_id`.
- `step` says how far it got. `W1` fills the Create New Task form; `W2` is the **Submit** click and its checks; `W3` is Hold; `W4` is Link to Project; `W5` is Solved. **From W2 on, the task may exist in MySys.**
- `detail` is a fixed sentence from the code, never page text.

**Exit codes:** 0 run finished (bookings and skips are normal; a `HOLD_LOST` alert also exits 0) · 1 run stopped (unexpected screen, Note Pool more pages, failed write, partial write, guard refusal, or killed at the time limit) · 2 config, secrets, login or wrapper setup problem · 3 accuracy breach.

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
   Check: `launchctl print gui/$(id -u)/au.com.prompteng.po-agent` (as `poagent`) now says it can't find the service. If a run was going (from :07, for up to 20 minutes), it is stopped too and may leave a Note with the agent: check for one (3.3) before you restart. Between about :30 and :05 no B1 run is going.
2. **The kill switch** (Joey): `enabled = false` in the site's config on `main` (`config/live.toml` after go-live, `config/test.toml` for test runs), through a pull request. The next run reads it from `main` whatever commit the `production` tag is on, logs `wrapper: enabled = false on main, agent not run`, runs nothing, opens no alert and exits 0.

While the job is unloaded, the heartbeat check will open `po-agent heartbeat missed` once 2 hours inside the schedule have passed, at its next weekday-afternoon check. That is expected: leave it open until runs are back. The Healthchecks.io check goes down within about an hour too and emails Joey; if the stop is planned, Joey can **Pause** the check in Healthchecks.io (the next ping resumes it). The kill switch doesn't trip either alert: each run still ends and pings.

These stop B1 and, through the site's switch (`config/live.toml`), Summit too. Unloading B1's job leaves Summit's running; to stop Summit too, also do 3.1a step 1.

### 3.1a Stop Summit alone

B1 keeps running. Either one stops the next Summit run:

1. **Unload Summit's job**, as `poagent`:
   ```bash
   launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent.summit
   ```
   Or as an admin: `sudo launchctl bootout gui/$(id -u poagent)/au.com.prompteng.po-agent.summit`. Check: `launchctl print gui/$(id -u)/au.com.prompteng.po-agent.summit` says it can't find the service. If a Summit run was going (from :30, for up to 20 minutes), it is stopped too and may leave a Note with Agent 2: check for one (3.3) before you restart.
2. **Summit's kill switch** (Joey): `enabled = false` in `config/clients/summit.toml` on `main`, through a pull request. The next Summit run logs `wrapper: enabled = false on main, agent not run` and exits 0; B1 is untouched.

**Then, while Summit stays stopped, delete its leftover download folders** (B1's runs no longer clear Summit's; one may hold a Summit PO PDF; decisions, 25 Nov 2026, per-client run controls). Once no run is going (`pgrep -fl macmini-run.sh` prints nothing), as `poagent`:

```bash
ls -d "$TMPDIR"po-agent-dl-summit-* /tmp/po-agent-dl-summit-* 2>/dev/null
rm -rf "$TMPDIR"po-agent-dl-summit-* /tmp/po-agent-dl-summit-*
```

Delete them, don't copy them. Joey can **Pause** the `po-agent summit` check in Healthchecks.io while Summit is stopped on purpose.

### 3.2 Restart the agent

1. Fix the cause first (the alert's entry in section 4), and make sure no Pending Note is still assigned to the agent (3.3), or the next run stops at the start.
2. If code or the site's config had to change: Joey merges the fix to `main`, tries it on the test site from the laptop (the live job keeps running) and moves the `production` tag to it (`docs/macmini-setup.md` section 8). Nobody else moves the tag. If Joey set `enabled = false`, he sets it back to `true` on `main`. The agent also reads `enabled` from the tagged commit's config, so the tag must be on a commit whose config says `true`: if the tag was moved while `main` said `false`, Joey moves it again after setting `true`.
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

**Summit:** the same steps with Summit's names. Step 1: no Pending Note with **Agent 2 (Summit Homes)** (3.3). Step 2: Summit's own switch is `enabled` in `config/clients/summit.toml`; both it and the site's must say `true`, on `main` and at the tag. Step 3 (not within a few minutes of :30, and only when `pgrep -fl macmini-run.sh` prints nothing):
```bash
~/po-agent/scripts/macmini-run.sh spike live summit
tail -20 ~/Library/Logs/po-agent/runs.log
```
Healthy as above, with `"client": "summit"` in the `RUN_SUMMARY`. Steps 4-5 with Summit's job:
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/au.com.prompteng.po-agent.summit.plist
launchctl print gui/$(id -u)/au.com.prompteng.po-agent.summit | head -30
launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent.summit
```
The `kickstart` books (up to `max_notes_per_run`); skip it to wait for the next :30.

### 3.3 Find a Note and its project in MySys

Log in to MySys (live after go-live, else the test site) with your own account. Get the `<note_id>` from the Mac Mini (section 2): the alert issue doesn't carry it.

1. **Note Pool:** Assigned Pool = **All Pools**, Assigned User = **All Users**, Locked/Unlocked = **All**; type `<note_id>` in Search/filter, then press **Refresh**. Use the row whose ID is exactly `<note_id>` (the search also matches longer IDs). The Status filter decides which Notes show: Pending lists only Notes not yet Solved.
2. The row shows the Note's Assignee and Status. **Still with the agent** means Assignee "Agent 1 (MySys Only)" and Status Pending.
3. Open the Note. Its attachment is named `<internal no>_048.pdf` (sometimes with `_1` before `.pdf`); the PO number is `<internal no>/048`.
4. **Project:** Project → Projects, search `<internal no>`, and open the row with Company **B1 Homes** and Client Ref No. exactly `<internal no>`. Its `pln_...` is the `<pln>`.
5. On the project's **Tasks** tab, look for Compaction Test tasks that aren't Cancelled. A task the agent made has Lodged By "Agent 1 (MySys Only)".

**Summit:** step 2: still with the agent means Assignee **"Agent 2 (Summit Homes)"** and Status Pending. Step 3: the Note's title carries the PO number (`<internal no>/...`); the PDF keeps its own name (MySys may file a `-` in it as `_`). Step 4: search the PO number's part before the first `/` and open the row whose Client Ref No. is exactly that and whose Company is a Summit company (`config/clients/summit.toml`). Step 5: Lodged By "Agent 2 (Summit Homes)".

**Who had a Summit Note before Agent 2** (its original assignee): open the Note; its log's "User Assigned" line for Agent 2's take names who had it (a person, a pool such as PO Allocation Pool, or nobody: `---`).

### 3.4 Return a Note to the agent's pool by hand

Only for a Note the agent took but where **no task was created** for it (no new non-Cancelled Compaction Test task on its project).

1. Open the Note (3.3).
2. Untick **Send Email Notification**.
3. User list: `--Select User--`. Pool list: **PO Allocation Pool** on live (**Agent Pool** on test). Press **Assign** once.
4. Check: Assignee reads that pool, Status Pending.

The next run picks it up again. Never use Unassign or Unlink.

### 3.4a Give a Summit Note back by hand

**Summit** only, for a Note Agent 2 took where **no task was created** for it. The agent gives a Note back to whoever had it; when it can't (the `ALERT UNEXPECTED_SCREEN` "run stopped; Note not returned", section 4), the Note stays with Agent 2 and **every later Summit run stops at the start** ("a Note is still assigned to the agent from an earlier run") until a person does this. B1 is unaffected.

1. Find the Note and who had it before Agent 2 (3.3, Summit). If "Assignee:" already reads `---` (the agent's own Unlink worked but its log check failed), stop here: it is back.
2. Open it and untick **Send Email Notification**.
3. Give it back:
   - **It had nobody (`---`)**, the usual case for a new Summit email: press the red **Unlink** button beside "Assignee: Agent 2 (Summit Homes)". "Assignee:" now reads `---` (the admins' own practice; decisions, 26 Nov 2026, S.0 live findings). Since 27 Nov 2026 the agent presses this same Unlink itself (`unlink_assignee`), so you only need to when its own try failed.
   - **It had a person:** User list = that person, Pool list `--Select Pool--`, press **Assign** once.
   - **It had a pool:** User list `--Select User--`, Pool list = that pool, press **Assign** once.
4. Check: "Assignee:" reads the original assignee (or `---`), Status Pending. The next Summit run goes on by itself.

**The agent's own `---` return (from 27 Nov 2026, once the `production` tag includes it):** a Summit run that took a `---` Note and stopped before Submit presses the Assignee block's Unlink itself. Its first time on live is the only real proof (Summit has no seam 2). After a Summit `ALERT` that is **not** "Note not returned", as `poagent`: `grep unlink_assignee ~/Library/Logs/po-agent/trace/<YYYY-MM-DD>.jsonl`. A line there means the agent pressed it: check that run's `read_back.assignee`, `read_back.log_line` and `read_back.unlink_button` lines all say `pass`, then in MySys (3.3) that the Note reads "Assignee: ---", has one new log line "Unassigned from Agent 2 (Summit Homes) to", and that no email went out. Tell Joey either way.

### 3.5 Finish a booking by hand

For a Note the agent left after the **Submit** click (step W2 to W5). The goal is what the agent would have done. Do only the parts that aren't done yet, with your own account.

1. Open the project `<pln>` (3.3), Tasks tab. Count the non-Cancelled Compaction Test tasks made for this PO:
   - **None:** the Submit didn't create one. Return the Note (3.4) and stop here.
   - **More than one:** keep one (the one with every value right) and **Cancel** the others.
   - **One:** go on.
2. **Check the task** (open it from its details row): PO Number `<internal no>/048`; Task Creator **Perth Scheduling**; **- Compaction Test** the only service ticked; Notes = the Note's body text; the task's own **Documents** tab lists the Note's PDF under **Client Documents**; and on the project's **Documents** tab, under that task, one row with the Note's PDF, Type **Client Documents** (on both sites; tasks booked before 12 Nov 2026 show Purchase Order and no Client Documents). Fix a wrong value by hand. If you can't, Cancel the task and book it by hand (3.6).
3. **Hold** (if its Status doesn't start "On-hold"): press **Hold** on that task's row. In the "Hold Task: `<task no>`" window, type `ON HOLD UNTIL CALL UP` in Note. Check that no related job is ticked (only this task is held), then press that window's **Hold**. The Status now starts "On-hold" and shows the note.
4. **Link** (if the Note has no project button showing `<pln>`): open the Note, untick **Send Email Notification**, press **Link to Project**, search `<pln>` and select it. If the Note is linked to a **different** project, use Change Project to put it on `<pln>`.
5. **Solved** (if the Note isn't Solved): untick **Send Email Notification**, then Status → **Solved**.
6. Leave the Note assigned to the agent. Once it is Solved, runs no longer stop on it.

**Summit:** the same steps, except: "None" in step 1 means give the Note back (3.4a); in step 2 the PO Number is the full PO number from the Note's title, the Task Creator is the creator table's for the project's company (`config/clients/summit.toml`; for a "previous task" company, the Task Creator of the project's highest-numbered task that is not a Compaction Test and not Cancelled), and the PDF's name may show a `-` as `_`; the Note stays with Agent 2 once Solved.

### 3.6 Book a PO by hand

Only when a task had to be cancelled in 3.5. On project `<pln>`: **Create New Task**. Creator (Client section) = **Perth Scheduling**; tick **- Compaction Test**; PO Number = `<internal no>/048`; upload the Note's PDF to **Documents** (not PO Documents, which never reaches the task's Client Documents; decisions, 12 Nov 2026); Note = the Note's body text; leave everything else as it is; **Submit**. Then 3.5 steps 3 to 6. **Summit:** Creator and PO Number as 3.5's Summit paragraph says.

### 3.7 Change the MySys password in the Keychain

When the agent account's password has changed (or was reset). The live account's items are `mysys_live_password` and `mysys_live_username`; the test site's `mysys_test_password` and `mysys_test_username`:

1. Get the new password from whoever changed it (the MySys admin) or the company password manager. Keep it there; don't send it anywhere.
2. Log in at the Mac as `poagent`. In Terminal:
   ```bash
   cd ~/po-agent
   uv run keyring set po-agent mysys_live_password
   ```
   It asks for the password: type it (nothing shows) and press Return.
3. Check the items: `cd ~/po-agent && uv run po-agent preflight --site live` (both `ok`; it prints no values and doesn't log in). Then run one spike: `~/po-agent/scripts/macmini-run.sh spike live` (not within a few minutes of :07).
4. If macOS asks whether Python may use the "po-agent" item in your keychain, type the `poagent` macOS password and choose **Always Allow**. If it asks again (once per item), choose **Always Allow** again. A run left waiting on this dialog is killed after 20 minutes and alerts.
5. Check `runs.log`: `INFO  logged in` and `"exit_code": 0` in the last `RUN_SUMMARY`.
6. Lock the screen (Control-Command-Q).

**Summit's Agent 2 (Summit Homes):** the MySys admin says its password has no expiry date and its login has no MFA (S.0, 26 Nov 2026), so it changes only when someone changes it. If it does, the same steps with its own items, `mysys_live_summit_password` (and `mysys_live_summit_username`), and Summit's checks:
```bash
cd ~/po-agent
uv run keyring set po-agent mysys_live_summit_password
uv run po-agent preflight --site live --client summit
~/po-agent/scripts/macmini-run.sh spike live summit
```
The spike: not within a few minutes of :30, and only when `pgrep -fl macmini-run.sh` prints nothing. A wrong Agent 2 password gives `ALERT LOGIN_FAILED` on Summit runs only; B1 keeps running.

The username works the same way with `mysys_live_username`. For the test site, use the `mysys_test_` names and `spike test`.

### 3.8 Who is told

- **Joey:** GitHub emails him about every alert issue, automatically, and Healthchecks.io emails him when its check is down or up again (his account; nobody else gets those).
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
  - **Summit: "run stopped; Note not returned"** (often with a `reason=`, for example `reason=CREATOR_UNKNOWN`): Agent 2 took the Note, stopped before Submit and couldn't give it back. For a Note whose assignee was `---`, the agent's own Unlink (decisions, 27 Nov 2026) was refused or didn't read back: **first open the Note and read "Assignee:"**. If it already reads `---`, the Unlink worked and only its log check failed: the Note is back, nothing more to do in MySys, tell Joey. Nothing was submitted. Otherwise give it back by hand (3.4a); until then every Summit run stops at the start with the next detail.
  - **Summit: "a Note is still assigned to the agent from an earlier run"**: a Pending Note sits in Agent 2's My Notes. Either an earlier Summit run left it (above) or a person assigned a Note to Agent 2 by hand (nobody should, from go-live step S.1). Find it (3.3) and give it back (3.4a), or finish it (3.5) if a task was made. Then runs go on by themselves.
  - **Summit, step W1, `reason=CREATOR_UNKNOWN`** ("creator not an option"): the creator the table gives for the project's company isn't in that project's Creator list, so nothing was selected or submitted. Give the Note back if it is still with Agent 2 (3.4a), book the PO by hand if it is due, and tell Joey: the creator table (`config/clients/summit.toml`) or the project's Creator list has changed. The same Note will stop at W1 again on the next runs until it is fixed.
  - **Summit, step W1, "project changed since the decision"**: for a "previous task" company, the project's tasks changed between the agent's read and W1. Nothing was submitted; the Note was given back (or, if `---`, see "Note not returned" above). The next run decides again.
  - **Anything else** (for example "unexpected error (type=...)", "Note not found once"): nothing was submitted and the Note was handed back. Nothing to undo. If the alert has step W2 to W5, treat it as `PARTIAL_WRITE` (3.5).
- **Restart:** the next run tries again by itself. If the same alert comes **two runs in a row**, POs aren't being booked: stop the agent (3.1) and tell Joey that a MySys screen may have changed.
- **Told:** Joey (automatic).

### MORE_PAGES (exit 1)

- **Means:** the Note Pool's list has a second page, which the agent never reads, so it stopped before taking any Note. The detail is "Note Pool has more pages: stale-Note read incomplete" (test: the check of all Pending Notes, any pool or user), "My Notes has more pages: stale-Note read incomplete" (live: the agent's own My Notes tab, so the agent holds more Pending Notes than fit on one page) or "Note Pool has more pages: page 2 not read" (the PO Allocation Pool + Locked list is over one page, 50). On live a My Notes row already stops the run as `UNEXPECTED_SCREEN`, so the My Notes detail is rare.
- **In MySys:** nothing to undo. The count of Pending Notes has to come down below one page. Which Notes to deal with first is Joey's call.
- **Restart:** every run stops with this alert until the count is down; then the next run goes on by itself. If it will take more than a day, stop the agent (3.1) to save the hourly alerts.
- **Told:** Joey (automatic).

### HOLD_LOST (exit 0: the run goes on)

- **Means:** at the start of a run, before taking any Note, the agent re-read a Compaction Test task it booked today or on the previous working day, and the task is no longer On Hold (decisions, 11 Nov 2026, hold re-check). The detail is "booked task not on hold" (the task's row has no **Un-Hold**, or its Status doesn't start "On-hold": on 11 Nov 2026 a live task was found back at "New Project" with the **Hold** button and no Un-Hold in any log) or "booked task not found" (the project no longer matches the internal number, or the task isn't on it). The agent only read: it changed nothing. A Cancelled task never alerts. The `note_id` is the booked Note's.
- **Find the task:** on the Mac Mini as `poagent`, `grep '"note_id": "<note_id>"' ~/Library/Logs/po-agent/runs.log` gives the Note's `"outcome": "booked"` line with its `pln` and `task_id` (or `grep '"name":"booked"' ~/Library/Logs/po-agent/trace/<YYYY-MM-DD>.jsonl` for that day's bookings). Open project `<pln>` (3.3), Tasks tab, and find `<task_id>`.
- **In MySys:** if the project's **Log** shows a person un-held it on purpose (the builder called up), there is nothing to do. Otherwise hold it again by hand as in 3.5 step 3, with your own account, and tell Joey: it may be the silent release seen on 11 Nov 2026, whose cause Joey is asking the MySys admin. "Not found": look for the task on the project (3.3) and tell Joey; never create one.
- **Restart:** nothing stopped. Each run alerts again while the task is not held and was booked today or on the previous working day; then the re-check no longer reads it. In the issue comment, give only the run_id and what you did (on live no pln or task number: the repository is public).
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
  - To see which items are not `ok` before fixing: `uv run po-agent preflight --site live` as `poagent` (3.7 step 3).
  - **"secret store unavailable"**: the Keychain couldn't be read, usually because it is locked. Log in at the Mac as `poagent`, run one spike (3.7 steps 3 to 6), and lock the screen.
  - **"leftover download folder not removed"**: a temp folder from an earlier run couldn't be deleted. **First make sure no run is going** (as `poagent`, `pgrep -fl macmini-run.sh` prints nothing): the folders of a run going now (B1's or Summit's) match the same names. Then as `poagent`: `ls -d "$TMPDIR"po-agent-dl-* /tmp/po-agent-dl-*` shows them (Summit's are `po-agent-dl-summit-*`); `rm -rf "$TMPDIR"po-agent-dl-* /tmp/po-agent-dl-*` deletes them. It may hold a PO PDF, so delete it, don't copy it. If that fails too, restart the Mac (`docs/macmini-setup.md` section 10).
  - **"config file not readable"**, **"config file is not valid TOML"**, **"invalid config value"**, **"unknown site"**, **"config file is for another site"**, **"unknown time zone"** or **"invalid command line"**: the code or the site's config (`config/live.toml` or `config/test.toml`) at the `production` tag is wrong. Joey fixes it on `main` and moves the tag.
- **Restart:** after a Keychain or folder fix, run one spike (3.2 step 3); scheduled runs then go on. For a config fix, Joey restarts (3.2 step 2).
- **Told:** Joey (automatic).

### RUN_LOCK_STUCK (exit 1)

- **Means:** another run has held the run lock for over an hour. Runs take minutes and the wrapper kills a scheduled run at 20 minutes, so this is a hung manual run (or a hung process outside the wrapper). Nothing in MySys changed by this run, which did not start. Every hourly run raises it again until the holder ends. A lock held for less than an hour is normal (a manual run overlapping) and prints only `INFO  run lock held: run not started`, exit 0, with no alert.
- **Do:** as `poagent`, `ps aux | grep po-agent` finds the holder (its pid is in `~/po-agent/state/run-<site>.lock` for B1, `~/po-agent/state/run-live-summit.lock` for Summit; each client has its own lock, so a B1 run never holds Summit's or the other way round). If it is a manual run Joey left open, end it; the lock frees itself. Don't delete the lock file.
- **Told:** Joey (automatic).

### Summit lines that are not alerts

- **`NOTE ... "outcome": "untouched", "reason": "NOTE_TAKEN"`**: a person took the Note between Agent 2's read and its take, so Agent 2 left it alone. Nothing to do.
- **`NOTE ... "outcome": "untouched", "reason": "DECIDE_ONLY"`**: a `decide-only` run would have booked this Note; nothing was taken.
- **`NOTE ... "outcome": "untouched"` with another reason** (for example `COMPANY_UNKNOWN`, `DUPLICATE_TASK`): Agent 2 read the Note and decided not to book it; it never took it, so it is still where it was. The admins book it as before.

### 7.2's alert: no separate alert

Plan task 7.2 planned an "every Note skipped" alert (`ALL_SKIPPED`). It was never added, because it could never fire (decisions, 5 Nov 2026): the run already stops on its first `UNEXPECTED_SCREEN`, and a second page of Notes is `MORE_PAGES`. Use those two entries.

### Missed heartbeat (`po-agent heartbeat missed`)

- **Means:** no **B1** run has finished for more than 2 hours inside the schedule (07:07 to 17:30 Perth, weekdays). Every B1 run, even a failed one, updates the issue labelled `po-agent-heartbeat` (Summit runs don't), so this means runs aren't happening or can't reach GitHub. Nothing alerts at night, at weekends or in the first 2 hours of a day. GitHub runs the check about once each weekday afternoon (decisions, 18 Nov 2026), so runs that stopped in the morning are alerted about that afternoon, and runs that stopped after the day's check, the next weekday afternoon: they may have been down for most of a working day.
- **Check, in this order:**
  1. **Did someone unload the job on purpose** (after an earlier alert)? Then this is expected: leave it open until runs are back.
  2. **At the Mac** (the most likely cause; 18-19 Nov 2026): if it shows the FileVault unlock screen (after a power cut, restart or macOS update), or an admin account is logged in, or `poagent` isn't, follow "`poagent` logged out, or an admin session left on" below. If it is off, turn it on and do the same.
  3. **As `poagent`:** `launchctl print gui/$(id -u)/au.com.prompteng.po-agent | head -30`. If it can't find the service and nobody unloaded it on purpose, load it (3.2 step 4).
  4. `tail -50 ~/Library/Logs/po-agent/runs.log`: if recent runs are there with `wrapper: heartbeat not sent`, runs work but GitHub can't be reached: check the internet, and whether the Mac Mini's GitHub token has expired (it lasts 90 days; see the setup failure for `git fetch` below).
  5. A dialog on `poagent`'s screen asking for Keychain access: choose **Always Allow** (3.7 step 4).
- **In MySys:** nothing to undo. Notes wait in the pool until runs are back.
- **Restart:** once a run has finished (`RUN_SUMMARY` in `runs.log`), **close** the `po-agent heartbeat missed` issue (or ask Joey to, if your GitHub account can't). Another one opens if runs stop again.
- **Told:** Joey (automatic; GitHub emails him about this issue directly).

### Healthchecks.io down (an email, not an issue)

- **Means:** Healthchecks.io's check `po-agent b1-homes` got no ping within 40 minutes of a scheduled run (07:07 to 17:07 Perth, weekdays; decisions, 19 Nov 2026). Every run pings at its end, even a failed one, so runs aren't happening, or they run but can't reach Healthchecks.io. Comes within about an hour of the stop. A failed run is not this alert: it opens its own issue.
- **Check:** the same steps as Missed heartbeat above (an unload on purpose, the FileVault screen, a logged-out `poagent` or an admin left logged in (next entry), the job loaded, a Keychain dialog), except in step 4: if recent runs in `runs.log` show `wrapper: healthchecks ping not sent`, runs work but Healthchecks.io can't be reached (the internet, or Healthchecks.io itself); `wrapper: healthchecks ping not configured` means the URL is missing from `poagent`'s Keychain (Joey stores it again, `docs/macmini-setup.md` section 7). Runs with neither line and a `RUN_SUMMARY` mean the ping went: look at the check's page for its last ping.
- **In MySys:** nothing to undo. Notes wait in the pool until runs are back.
- **Restart:** as in 3.2 (log `poagent` in, lock the screen with Control-Command-Q, load the job if it is gone). Nothing to close: the next run's ping turns the check **up**, and Healthchecks.io emails that too. If the GitHub backup also opened `po-agent heartbeat missed`, close that once a run has finished.
- **Told:** Joey (automatic; only his Healthchecks.io account gets the email). The backup admin sees no email for this one: Joey asks them to go to the Mac if he is away.
- **Summit's check `po-agent summit`** (cron `30 7-17 * * 1-5`, 40-minute grace): the same, for Summit's runs at :30 and its job `au.com.prompteng.po-agent.summit` (in step 3 of Missed heartbeat, print and load that job instead). Its ping URL is Keychain item `healthchecks_ping_url_summit`. If only Summit's check is down, B1 is running: look for an unloaded Summit job (3.1a) first. If both are down, the Mac or `poagent` is the cause (next entry).

### `poagent` logged out, or an admin session left on

- **Means:** the job is a LaunchAgent in `poagent`'s session and needs its login Keychain, so it runs only while `poagent` is logged in (locked is fine). On 18-19 Nov 2026 a macOS update restarted the Mac, the admin account stayed logged in, and the screen lock logged `poagent` out: no run for about 15 working hours (decisions, 19 Nov 2026, Mac Mini outage). The same happens after a power cut or any restart, until someone unlocks as `poagent`.
- **Signs:** a Healthchecks.io down email or a `po-agent heartbeat missed` issue; no new lines in `runs.log` after a :07; the Mac shows the FileVault unlock screen, or a login window listing `poagent` and an admin; from an admin account, `who` doesn't list `poagent` on `console`.
- **Fix, at the Mac:**
  1. If an admin account is logged in: unlock it and **log it out** (Apple menu → Log Out). Don't just switch users.
  2. Unlock as **`poagent`** (from the FileVault screen or the login window).
  3. As `poagent`: `launchctl print gui/$(id -u)/au.com.prompteng.po-agent | head -30`. If it can't find the service, load it (3.2 step 4).
  4. Lock the screen: Control-Command-Q. Don't log `poagent` out.
  5. After the next :07, as `poagent`: `tail -20 ~/Library/Logs/po-agent/runs.log` shows a new `RUN_SUMMARY`. To not wait, start one now with `launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent` (3.2 step 5; not within a few minutes of :07).
- **In MySys:** nothing to undo. Notes wait in the pool until runs are back.
- **Restart:** once a run has finished, close the `po-agent heartbeat missed` issue if one opened; the Healthchecks.io check turns **up** by itself.
- **Prevent:** only `poagent` stays logged in; an admin logs out before leaving the Mac; after a macOS update, unlock as `poagent` and lock the screen (`docs/macmini-setup.md` sections 5 and 10).
- **Told:** Joey (automatic, through either alert).

### Wrapper setup failed (exit 2)

The issue (`po-agent alert no run_id`) holds `wrapper: setup failed (<step>), agent not run` and `exit code: 2`. The Mac Mini fetches the code and checks the switch before each run; when that fails, the agent doesn't run at all and never falls back to older code on disk. Nothing in MySys changed. For more, as `poagent`: `tail -50 ~/Library/Logs/po-agent/launchd.log`.

| `<step>` | Means | Fix |
|---|---|---|
| `git fetch` | The Mac Mini couldn't reach GitHub: internet down, or its GitHub token expired | Internet: wait, the next run tries again. Token: as `poagent`, `cd ~/po-agent && git fetch origin` shows an authentication error. Joey makes a new token (`docs/macmini-setup.md` section 1), then as `poagent`: `gh auth login --hostname github.com --git-protocol https --with-token`, type it, then Control-D. An expired token also stops alert issues and the heartbeat, so this one often arrives as a missed heartbeat |
| `enabled on main` | The site's config (`config/live.toml` or `config/test.toml`), or for Summit also `config/clients/summit.toml`, on `main` doesn't have exactly one `enabled = true` or `enabled = false` line | Joey fixes `main` |
| `production tag missing` | There is no `production` tag | Joey creates it (`docs/macmini-setup.md` section 8). Nobody else |
| `git checkout` | The tagged code couldn't be checked out, usually because a file in `~/po-agent` was edited by hand | As `poagent`: `cd ~/po-agent && git status`. For each file it lists as modified: `git restore <file>` (this throws away the hand edit; nobody should edit files there). Then run one spike (3.2 step 3) |
| `uv sync` or `playwright install` | Installing the agent's packages or browser failed: internet down or disk full | Check the internet and free disk space; the next run tries again |

**Restart:** none needed: each scheduled run tries the setup again. Check the next run's `wrapper: running production <commit>` line.
**Told:** Joey (automatic). The tag and `main` fixes are his.

### Other `wrapper:` lines

- **`wrapper: agent killed at the 1200s limit`** (exit 1, in the alert issue): the run took over 20 minutes and was stopped. Usual causes: a Keychain dialog waiting for a click (3.7 step 4) or MySys very slow. A Note it was working on may be left with the agent: the next run then stops with `UNEXPECTED_SCREEN` "a Note is still assigned to the agent from an earlier run"; follow that entry.
- **`wrapper: alert issue not opened`** (in `runs.log` only): GitHub couldn't be reached, so an alert wasn't raised. Read the `ALERT` lines just above it in `runs.log` and act on them as if the issue had opened. Then check the internet and the GitHub token (`git fetch` above).
- **`wrapper: heartbeat not sent`** (in `runs.log` only): the run's ping didn't reach GitHub. Two hours of this inside the schedule opens `po-agent heartbeat missed` at the next weekday-afternoon check.
- **`wrapper: healthchecks ping not sent`** (in `runs.log` only): the run's Healthchecks.io ping failed (no internet, or Healthchecks.io down). The run itself is unaffected. Once in a while is fine; on every run the check goes down and emails Joey.
- **`wrapper: healthchecks ping not configured`** (in `runs.log` only): no Healthchecks.io ping URL in `poagent`'s Keychain, so no ping is sent. Expected until Joey stores it (`docs/macmini-setup.md` sections 1 and 7); after that, Joey stores it again.
- **`wrapper: enabled = false on main, agent not run`**: not an alert. The kill switch is on; runs start again when Joey sets it back to `true`.
- **`wrapper: leftover Playwright browser killed`**: not an alert. Housekeeping after a run: only that run's client's browsers (Summit's live in their own folder, `~/Library/Caches/ms-playwright-summit`), so a B1 run never kills a Summit run's browser or the other way round.
- **`wrapper: unknown client, agent not run`** (exit 2, in a `po-agent alert no run_id` issue): the wrapper was started with a third argument other than `summit`, so nothing ran. Its `runs.log` header reads `=== <time> macmini-run.sh <mode> <site> ? ===` (the argument itself is not written). A launchd plist copied wrong, or a typo in a run by hand: check `~/Library/LaunchAgents/au.com.prompteng.po-agent.summit.plist` says `run`, `live`, `summit` (`docs/macmini-setup.md` section 8).

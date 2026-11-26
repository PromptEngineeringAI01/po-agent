# Mac Mini setup — PO Agent (office Mac Mini, test site first)

**Version:** 1.7 · 26 Nov 2026 (1.7: Summit Home's run, task 9.15: the wrapper's `summit` argument, the second job at :30, its Healthchecks check, Agent 2's Keychain items, steps S.1-S.5 and stopping Summit alone (section 13); decisions, 26 Nov 2026, Summit on the Mac Mini. 1.6: a rollback to a commit from before task 9.5 stops the hold re-check on later bookings; check them by hand (decisions, 25 Nov 2026, per-client run controls). 1.5: read Claude's release summary and answer its teach-back before moving the `production` tag (decisions, 25 Nov 2026, loop review; teach-back). 1.4: a laptop test-site run no longer unloads the live job (decisions, 20 Nov 2026, one Send Email control). 1.3: release pinning, task 7.4: the wrapper runs the `production` tag, which only Joey moves; `enabled` is read from `origin/main`; how to move the tag and roll back. 1.2: plan freeze, decisions D1, D6 and D7: wrapper mode mapping, no run after a failed pull, process-group kill, stderr dropped; job unloaded after the S1 spike and loaded only for the first bookings and from M6; one agent at a time; the stale-Note stop. 1.1: "This Mac Mini" check for the office's model A3238) · **Owner:** Joey Wu · **Spec:** `SPEC.md` → Trial conditions, Commands · **Decision:** CEO decision 3 (`docs/decisions.md`, 15 Oct 2026; `docs/specs/ADR-002-po-agent-hosting.md`)
Do this in slice **M1**, once `pyproject.toml`, `uv.lock`, `po-agent spike`, `scripts/macmini-run.sh` and `scripts/au.com.prompteng.po-agent.plist` exist on `main`. Section 2 (the test login) can be done today.

The Mac Mini runs the agent for the MVP trial and, after go-live sign-off, for production. During the MVP it holds **test-site credentials only** and no real client data on disk. The one exception: the 3 trial POs are real, and runs read them from the test site in memory (`SPEC.md` → Trial conditions; the CEO confirms decision 2 before the first such run).

## This Mac Mini (model A3238)

The office Mac Mini is model **A3238**: the 2024 Mac mini with the **M4** chip, model ID **Mac16,10** (Apple silicon). The model number is printed on the underside. Every step below assumes Apple silicon; nothing else in this file depends on the model.

**Check it**, as an admin in Terminal:

| Check | Healthy |
|---|---|
| `sysctl -n hw.model` | `Mac16,10` (`Mac16,11` would be the M4 Pro, model A3239; the steps are the same) |
| `uname -m` | `arm64` |
| `sw_vers -productVersion` | The macOS version. Note it in the company password manager entry for this Mac, so later updates (section 5) can be checked against it |

**Set it up:**

- **Wired network:** plug an Ethernet cable from the Ethernet port on the back into the office router or switch, and use that rather than Wi-Fi for the hourly runs. System Settings → Network should show **Ethernet: Connected**.
- **A keyboard and a display stay with it.** After any restart the Mac waits at the FileVault screen until someone logs in as `poagent` (section 10), and that needs a keyboard and a screen at the Mac.
- **Power button:** it's on the **underside**, near the back edge. You only need it if the Mac doesn't start by itself after a power cut (section 4 sets that up).
- **No Rosetta.** uv, Python 3.12, `gh` and Playwright's Chromium all have native Apple silicon builds. If macOS offers to install Rosetta during setup, decline. Homebrew installs into `/opt/homebrew`, which is already on the wrapper's `PATH` (section 8).

## 1. Before you start

- [ ] The repo is on GitHub (public since 25 Oct 2026, so nothing real goes in it; decisions, 9 Nov 2026, go-live plan item 3) and `main` has M1's code.
- [ ] The test-site agent account username and password, and confirmation that it has no MFA (SPEC open question 3).
- [ ] A GitHub label for alerts. On your laptop: `gh label create po-agent-alert --color B60205`
- [ ] The heartbeat issue (task 7.1, section 8), once. On your laptop: `gh label create po-agent-heartbeat --color 0E8A16`, then `gh issue create --label po-agent-heartbeat --title "po-agent heartbeat" --body "no run yet"`. Lock it (`gh issue lock <number>`), so nobody can comment on it. Keep it open, and keep it the only open issue with that label.
- [ ] **The Healthchecks.io check** (decisions, 19 Nov 2026; Joey, by hand, once). Sign up at healthchecks.io (free Hobbyist plan) with Joey's work email, so its alerts reach him. In the project, **Add Check**: name `po-agent b1-homes`; **Schedule** → **Cron**, expression `7 7-17 * * 1-5`, time zone `Australia/Perth`, **grace time 40 minutes** (a run lasts up to 20 minutes, plus setup and two `gh` calls, and the ping comes at its end); **Integrations**: email to Joey on. Leave the check's page open: its **ping URL** (`https://hc-ping.com/...`) is the secret you store as `poagent` in section 7. Never paste it into a chat, a file, an issue or the repo; whoever has it can make the check look healthy. Until the URL is stored, each run logs `wrapper: healthchecks ping not configured`, and the check stays **new** (no alerts) until its first ping.
- [ ] A **fine-grained GitHub token** for the Mac Mini: github.com → Settings → Developer settings → Fine-grained tokens → **Generate**. Name `po-agent-macmini`; resource owner `PromptEngineeringAI01`; **only** the `po-agent` repository; permissions **Contents: Read-only**, **Issues: Read and write** (Metadata: Read-only is added automatically); expiry 90 days (diarise the renewal).
- [ ] The `production` tag on GitHub (section 8, "Moving the production tag"), before the job is loaded: without it every run alerts and runs nothing.
- [ ] A place in the company password manager for: the `poagent` macOS password, the backup admin's password and the FileVault recovery key.

## 2. Test MySys login from the Mac Mini first

Before installing anything, prove MySys accepts a login from the office internet address (ADR-002 action item 2).

1. On the Mac Mini, open Safari and go to `https://test-prompt.mysys.com.au/index.php?option=com_cweb&view=management&tmpl=component`.
2. Log in by hand with the **test-site agent account**. Never the live site.
3. Healthy: the management page loads; no CAPTCHA, "new device" challenge, MFA prompt or block page. Open the **Agent Pool** filter once to check it renders.
4. Log out and quit Safari (Safari → Clear History for the test site if you saved nothing else).

If MySys blocks or challenges the login: stop here, record it in `docs/decisions.md`, and tell the CEO; decision 3 assumed the office address works.

## 3. Accounts and disk encryption

System Settings → **Users & Groups**:

| Account | Type | Who | Why |
|---|---|---|---|
| Joey's account | Administrator | Joey | Setup and macOS updates |
| Backup admin | Administrator | The named backup maintainer | ADR-002 gate H5: two people can administer the host |
| `poagent` (full name "PO Agent") | **Standard** | Nobody day to day | Runs the agent; holds its secrets in its own Keychain |

- **FileVault: on** (System Settings → Privacy & Security → FileVault). Allow all three accounts to unlock the disk. Put the recovery key in the company password manager, not on the Mac.
- **Automatic login: off.** macOS greys it out while FileVault is on. This is deliberate (`docs/decisions.md`, 15 Oct 2026): an encrypted disk protects the agent's credentials if the Mac is stolen; the cost is that after an unplanned restart someone must log in (section 10).
- Never install Claude Code or any AI tool for `poagent`. No AI session may read its Keychain (ADR-002 gate H2). **Test site only, from 6 Nov 2026:** Joey runs Claude in `poagent` for another project (`docs/decisions.md`, 6 Nov 2026). Never in `~/po-agent`, never near the agent's Keychain items or logs, no second `gh` login; remove it from `poagent` before any live credential goes on this Mac.
- Optional: **Remote Login** (System Settings → General → Sharing) for the two admin accounts only, key-based, so Joey can read the log and stop the job without being in the office.

## 4. Power and clock

As an admin, in Terminal:

```bash
sudo pmset -a sleep 0 disksleep 0 displaysleep 10 powernap 0 autorestart 1
sudo systemsetup -settimezone Australia/Perth
sudo systemsetup -setusingnetworktime on
```

Then in System Settings → **Energy**: turn on **Prevent automatic sleeping when the display is off** and **Start up automatically after a power failure** (the same as `autorestart 1`).

Check:

| Check | Healthy |
|---|---|
| `pmset -g` | `sleep 0`, `autorestart 1` |
| `sudo systemsetup -gettimezone` | `Time Zone: Australia/Perth` |
| `date` | Shows `AWST` and the right time |

Plug the Mac Mini and the office router into a UPS if one is available.

## 5. macOS updates (outside 07:00–18:00)

System Settings → General → Software Update → **Automatic updates** (ⓘ):

- **Check for updates**: on. **Download new updates when available**: on.
- **Install macOS updates**: off. **Install application updates from the App Store**: off. **Install Security Responses and system files**: off.

Nothing installs by itself, so nothing restarts the Mac during run hours. Joey (or the backup admin) installs updates **after 18:00 on a weekday or at the weekend**, at least monthly and within 7 days of a security update, then logs the admin account **out**, unlocks as `poagent`, locks the screen and checks the next run (section 10). After an update, check the settings above are still off.

## 6. Software for the agent

As an admin (once):

```bash
xcode-select --install          # git
# Homebrew from brew.sh, then:
brew install gh
```

As `poagent` (log in at the Mac):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh    # uv in ~/.local/bin
gh auth login --hostname github.com --git-protocol https --with-token   # type or paste the po-agent-macmini token, then Ctrl-D
gh auth setup-git
gh repo clone PromptEngineeringAI01/po-agent ~/po-agent
cd ~/po-agent
uv sync --locked
uv run playwright install chromium
```

`gh` stores the token in `poagent`'s login Keychain. Never put the token in a file, the repo or a chat.

## 7. Secrets

As `poagent`, in `~/po-agent`. Each command prompts for the value; type it yourself, never paste it into a chat or a file:

```bash
uv run keyring set po-agent mysys_test_username
uv run keyring set po-agent mysys_test_password
```

They go into `poagent`'s login Keychain (keyring service `po-agent`; names as `SPEC.md` → Secrets). Don't set any `PO_AGENT_*` environment variable on the Mac Mini.

**The Healthchecks.io ping URL** (Joey, once, after section 1's check; decisions, 19 Nov 2026). As `poagent`, in Terminal. `-w` last, with no value, makes it prompt (twice), so the URL never goes on the command line or into the shell history:

```bash
security add-generic-password -s po-agent -a healthchecks_ping_url -w
```

Type or paste the check's ping URL at the prompt. The wrapper reads it with `security find-generic-password` (section 8, step 7); an item made by `security` trusts `security`, so no Keychain dialog appears. To check it is there without showing it: `security find-generic-password -s po-agent -a healthchecks_ping_url > /dev/null && echo stored`. To replace it (a leaked URL): in Healthchecks.io create a new check as in section 1 and remove the old one, then `security delete-generic-password -s po-agent -a healthchecks_ping_url` and add it again as above.

**Live secrets (G.4; decisions, 10 Nov 2026, live profile).** Joey only, by hand, and only once ADR-002 H2 passes again (Claude and every other AI tool removed from `poagent`). The live agent account has its own pair, which `--site live` reads:

```bash
uv run keyring set po-agent mysys_live_username
uv run keyring set po-agent mysys_live_password
```

Summit's Agent 2 has its own pair, `mysys_live_summit_username` and `mysys_live_summit_password`, and its own Healthchecks item, `healthchecks_ping_url_summit`: section 13 (S.1 and S.5). Claude never reads, sets or names these values (CLAUDE.md Must never #3 and #5). The live password has no expiry (Joey's look at live, 10 Nov 2026); if the admin changes it, set the new one the same way, then run one live spike at the Mac.

**Check them before the first live run, and after any change to them (decisions, 20 Nov 2026, secrets pre-flight).** At the Mac as `poagent`:

```bash
cd ~/po-agent && uv run po-agent preflight --site live
```

It prints each secret's name and `ok`, `not set`, `malformed` (a stray space, tab or newline) or `store unavailable` (Keychain locked), never a value, and does not log in. Exit 0 and `INFO  preflight: secrets ok` mean both are there and well-formed; anything else exits 2: fix the named item (`uv run keyring set po-agent <name>`) and run it again. If macOS asks for Keychain access, choose **Always Allow**. A pass does not prove the password is right: only the live spike after it does. For the test site: `--site test`.

**Keychain trap:** a Keychain item trusts the program that created it. If uv installs a new Python (a new path), macOS shows an "allow access to the keychain" dialog and an unattended run waits for a click. So: keep Python pinned in `.python-version`; after any Python change, run one spike at the Mac as `poagent` (section 8) and click **Always Allow** for each item. The wrapper's 20-minute limit ends a run stuck on that dialog and raises an alert.

## 8. The scheduled job (launchd)

**The wrapper** `scripts/macmini-run.sh <run|spike|decide-only> <test|live> [summit]` does, in order. The site is required, with no default (decisions, 10 Nov 2026, live profile); a missing or unknown site, or any other argument, prints the usage message and exits 2 with nothing run. After go-live the job runs `run live` only. A third argument names the client (task 9.15): none is B1, exactly as before; `summit` is Summit Home's run (section 13); any other logs `wrapper: unknown client, agent not run`, opens the alert issue and exits 2 with nothing run. Where Summit's run differs, the step says so.

1. **Release pinning** (task 7.4) in `~/po-agent`: `git fetch --force --prune --prune-tags origin` (a moved tag updates, a deleted one disappears); reads `enabled` from `config/<site>.toml` (`config/test.toml` or `config/live.toml`) on `origin/main`; then checks out the commit of the **`production` tag** (detached HEAD) and logs `wrapper: running production <first 12 characters of the commit>` to `runs.log`. So a merge to `main` changes nothing on the Mac Mini until Joey moves the tag, but `enabled = false` on `main` still stops the next run: the wrapper logs `wrapper: enabled = false on main, agent not run`, checks out nothing and exits 0, with no alert issue. **Summit** also reads `enabled` from `config/clients/summit.toml` on `origin/main`: both must say `true`.
2. `uv sync --locked`, then `uv run playwright install chromium` (a no-op unless Playwright moved in `uv.lock`). Their own output goes to `launchd.log`.
   **If step 1 or 2 fails, the agent doesn't run**, and it never falls back to the code already on disk: a failed fetch, a missing `production` tag, a failed checkout (for example a file edited by hand in `~/po-agent`), the site's config on `origin/main` without exactly one `enabled = true` or `enabled = false` line, or a failed sync or install. The wrapper writes `wrapper: setup failed (<step>), agent not run` to `runs.log` and opens the alert issue (exit code 2).
3. Runs the agent with `--site <site>` and never `--detailed-log`: mode `run` → `uv run po-agent run`, `spike` → `uv run po-agent spike`, `decide-only` → `uv run po-agent run --decide-only`. It has a 20-minute hard limit. macOS has no GNU `timeout` or `setsid`, so the wrapper implements it: bash job control (`set -m`) starts the agent in its own process group, and the wrapper kills the whole group (uv, Python and Playwright's driver; SIGTERM, then SIGKILL 10 seconds later) at the limit, when the agent ends and when the wrapper itself is stopped. Playwright starts Chromium detached, in a group of its own, so the wrapper then also kills every Playwright browser of `poagent` of that client (`pkill -KILL -u <uid> -f ms-playwright/`, logged as `wrapper: leftover Playwright browser killed` when it finds one). Nothing is left to overlap the next run. **Summit** passes `--client summit` and keeps its own Chromium in `~/Library/Caches/ms-playwright-summit` (`PLAYWRIGHT_BROWSERS_PATH`, for its install and its run; its first run downloads it, about a minute), and kills only `ms-playwright-summit/`; B1's pattern doesn't match that folder, so neither client's run kills the other's browser. A run killed at the limit exits 1 and adds `wrapper: agent killed at the 1200s limit` to `runs.log`.
4. Appends the run's stdout (the stdout contract only: no PDF text, addresses or Note bodies) to `~/Library/Logs/po-agent/runs.log`, after a timestamp line per run (`=== <time> macmini-run.sh <mode> <site> ===`). The agent's stderr goes to `/dev/null`: the agent writes nothing there by design, and a crash's text could quote page content.
5. If the run printed an `ALERT` line or exited non-zero: `gh issue create --label po-agent-alert`, titled `po-agent alert <run_id, or "no run_id">`, whose body is only the `ALERT` lines **without any Note ID**, the wrapper's own fixed line (failed setup or time limit) if there is one, and `exit code: <n>`. The repo is public (audit N4; decisions, 9 and 10 Nov 2026): the wrapper cuts the JSON `note_id` key and the detail's `note_id=<id>`, and a line that still names one keeps only `ALERT <KIND>`. **The Note is named in `runs.log`**, which keeps every `ALERT` line whole (just above the run's `RUN_SUMMARY`), and in the safe trace (`grep <run_id>`, section 9; `docs/ops-runbook.md` section 2). The issue is opened with Joey's own token, and GitHub doesn't email you about your own actions, so `.github/workflows/alert-email.yml` has github-actions[bot] post one fixed comment on it ("po-agent alert: see the issue body."), which emails Joey as the issue's author (Joey's choice, 5 Nov 2026). If `gh` fails, `runs.log` gets `wrapper: alert issue not opened`. **Summit's** issues are titled `po-agent alert summit <run_id, or "no run_id">`.
6. **The heartbeat ping** (task 7.1), **B1's runs only** (Summit's leave the issue alone, so it keeps meaning "B1 ran"; plan Phase S, open question 4), at the end of every run, whatever the exit code: a failed setup, a run killed at the limit and a stopped wrapper ping too. The wrapper finds the one open issue labelled `po-agent-heartbeat` (section 1) and replaces its body with three lines: `last run: <UTC time>`, `exit code: <n>`, `run_id: <run_id, or "none">`. No PO data, no git push, no new secret (the same `gh` token). If the ping fails, `runs.log` gets `wrapper: heartbeat not sent`, and the run's exit code doesn't change. Every `gh` call (the alert issue and the ping) is killed after 60 seconds, so a hung `gh` can't hold the wrapper and make launchd skip the next runs.
7. **The Healthchecks.io ping** (decisions, 19 Nov 2026), right after step 6, every run too: a plain GET of the check's ping URL, whatever the exit code (failed runs already open an alert issue). The URL is read from `poagent`'s Keychain (`security find-generic-password -s po-agent -a healthchecks_ping_url -w`; section 7) and given to `curl` on stdin, never as an argument; `curl` gets 20 seconds an attempt, 2 retries and no retry after 40 seconds. Nothing of it is written anywhere: `runs.log` gets at most a fixed line. No URL in the Keychain: `wrapper: healthchecks ping not configured`. The ping failed (no internet, Healthchecks.io down): `wrapper: healthchecks ping not sent`. Neither changes the exit code or stops the GitHub ping. Healthchecks.io learns only the time of each run's end. Like every wrapper change, this starts only once the `production` tag is on it. **Summit** pings only its own check, Keychain item `healthchecks_ping_url_summit` (section 13); without it, `not configured`, never B1's URL.

**The Healthchecks.io check** (section 1) expects a ping after each scheduled run (cron `7 7-17 * * 1-5`, `Australia/Perth`). When none arrives within the 40-minute grace time after a :07, it turns **down** and emails Joey, so a stop is known within about an hour, at any time of the weekday schedule. When pings return it turns **up** and emails again; there is nothing to close. A `spike` run by hand pings too, which is harmless. It works when the Mac Mini is off. See `docs/ops-runbook.md`, "Healthchecks.io down".

**The missed-heartbeat check (backup)** is a scheduled GitHub Action (`.github/workflows/heartbeat.yml`, running `scripts/heartbeat_check.py`; Joey's choice, 5 Nov 2026), so it still works when the Mac Mini is off. **It is checked about once each weekday afternoon** (decisions, 18 Nov 2026): the cron asks for every 30 minutes on weekdays (09:07-19:37 Perth), but GitHub's scheduled workflows are best-effort, and from 13 to 17 Nov one firing a day came inside the schedule (15:47-17:02 Perth); the others came after Perth midnight, where the check sees a new day's schedule and checks nothing. Each time it runs, it reads the `last run:` time from the heartbeat issue's body (not its update time, so a comment or label can't pass for a ping) and counts how much of **today's schedule, 07:07-17:30 Perth**, has passed since then (17:30: the 17:07 run's ping, after its 20-minute limit). More than 2 hours opens an issue labelled `po-agent-alert` titled `po-agent heartbeat missed` (GitHub emails Joey). So nothing alerts at night, at the weekend or in the first 2 hours of a day, a normal end of day never alerts, and two missed runs in a row do, at the next check that runs inside the schedule. One missed run alone (about 2 hours between pings) doesn't. **When Joey hears:** runs that stop in the morning are alerted about that afternoon; runs that stop after the day's check, the next weekday afternoon. Meanwhile the Notes wait in the pool. Since 19 Nov 2026 the Healthchecks.io check above is the fast alert, and this one stays as a backup. While that issue is open and was opened after the last ping, no second one opens; **close it once runs are back**. An alert left open from an earlier outage doesn't hide a new one. It uses only the workflow's own `GITHUB_TOKEN` (`issues: write`, `contents: read`). GitHub disables scheduled workflows in a repo with no activity for 60 days: if it shows as disabled in the Actions tab, enable it again. To test it by hand: Actions → heartbeat → Run workflow.

**Moving the production tag** (Joey only, by hand, on the laptop; Claude never creates, moves or pushes it). Move it only to a commit on `main` that has passed CI and has run on the test site. **First read Claude's release summary** (decisions, 25 Nov 2026, loop review), in chat, never committed: every PR merged since the tag (`git fetch --force --tags origin`, then `git log --merges --first-parent production..<commit>`), the Risk level each one states in its PR body (`/verify-pr` checked it was not below `scripts/risk.py`'s, which can't be recomputed for a merged commit), and for each high-risk PR the one fact it is safe because of and its must-fix triage; then what is still unproven (for example a pending seam 2). This is where Joey sees the high-risk changes Claude merged. **Then a teach-back** (decisions, 25 Nov 2026, teach-back): for each high-risk PR, Claude asks Joey one question, one at a time, on what the change does or could break (for example "a creator alias is missing: what does the run do with that Note?"), and Joey answers in his own words before Claude explains. A wrong or unsure answer doesn't block the tag by itself: Joey decides whether to move it now or after reading that PR's diff, and Claude notes the gap in `learning/NOTES.md` (git-ignored, the `/teach` workspace) for a later lesson. The Mac Mini always runs the tag, so try a new commit on the test site from the laptop first (one laptop test-site run at a time; the live job keeps running).

```bash
git fetch origin
git tag -f production <commit>
git push --force origin refs/tags/production
```

The next scheduled run fetches the tag and runs that commit; check its `wrapper: running production <commit>` line in `runs.log`. The wrapper is part of the tagged code too, so a wrapper change also takes effect only once the tag moves (from the run after the one that checks it out). The first time, the tag doesn't exist yet: the same commands create it (`git tag production <commit>`, no `-f` needed).

**Roll back:** the same commands with an earlier commit; `runs.log`'s `wrapper: running production` lines show which commits ran. Never roll back to a commit from before task 7.4: its wrapper runs `git pull`, which fails on the detached HEAD, so every run would alert and run nothing. A rollback to a commit from before task 9.5 stops the hold re-check on every booking made since 9.5 (its trace reads a `booked` event with a `client` key as no booking), so check those tasks' On Hold by hand while it runs (decisions, 25 Nov 2026, per-client run controls). To stop runs at once instead, use section 11.

It sets its own `PATH` (`~/.local/bin`, `/opt/homebrew/bin`, then the system folders) because launchd starts jobs with a minimal environment, with an optional `MACMINI_RUN_PATH_PREFIX` in front so the wrapper's tests (`tests/test_macmini_wrapper.py`) can use stub commands. The tests also shorten the limit with `MACMINI_RUN_LIMIT_S`; the Mac Mini never sets either.

**The job** is a LaunchAgent in `poagent`'s own session (not a LaunchDaemon: keyring needs the login Keychain, which is only unlocked while `poagent` is logged in). Label `au.com.prompteng.po-agent`; the plist is in the repo as `scripts/au.com.prompteng.po-agent.plist`:

- `ProgramArguments`: `/Users/poagent/po-agent/scripts/macmini-run.sh`, `run`, `live` (after go-live the Mac Mini runs only live; decisions, 10 Nov 2026). Load it only at G.8 (hourly live runs); the watched live runs before that are started by hand (below). **At G.8, copy the plist again** with the `cp` line below before `launchctl bootstrap`: the copy in `~/Library/LaunchAgents/` from the test-site trial still runs `run` with no site, which the wrapper now refuses (usage message, exit 2), so every scheduled run would do nothing.
- `StartCalendarInterval`: one entry per weekday and hour, **Weekday 1–5 × Hour 7–17, Minute 7** (55 entries) → 07:07, 08:07 … 17:07 Monday–Friday, Perth time (the Mac's clock, section 4). Seven minutes past, as before, so a slow start never lands on the hour.
- `StandardOutPath` / `StandardErrorPath`: `/Users/poagent/Library/Logs/po-agent/launchd.log` (the wrapper's own errors; launchd doesn't expand `~`).
- No `RunAtLoad`, no `KeepAlive`.

launchd never starts the job while it is still running, and the agent's run lock (`state/run-<site>.lock` in the checkout, Summit's `state/run-<site>-summit.lock`; decisions, 21 Nov 2026) stops a manual run or any other process from overlapping it: the later run prints `INFO  run lock held: run not started` and exits 0. Don't delete the lock file; the OS frees the lock when its run ends, however it ends. The agent's own Perth-window check still applies (`run_window` in the site's config).

As `poagent`:

```bash
mkdir -p ~/Library/Logs/po-agent ~/Library/LaunchAgents
cp ~/po-agent/scripts/au.com.prompteng.po-agent.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/au.com.prompteng.po-agent.plist
launchctl print gui/$(id -u)/au.com.prompteng.po-agent | head -30    # state, last exit code
```

**Run now** (the scheduled `run` mode, immediately): `launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent`

**Spike and decide-only by hand:** as `poagent` in Terminal, `~/po-agent/scripts/macmini-run.sh spike test` (or `decide-only test`). Don't start a manual run within a few minutes of :07.

**The live order by hand (G.5-G.7; Joey only, at the Mac, never Claude):** `config/live.toml` is committed with `enabled = false`, so every live run does nothing until one PR flips it to `true` on `main`, just before G.5. **Then move the `production` tag to that PR's merge commit** (the commands under "Moving the production tag" above): the wrapper reads `enabled` from `main`, but the agent itself reads it from the tagged commit's `config/live.toml`, at the run start and before every write, so a tag left on a commit with `enabled = false` still stops every live run (`INFO  kill switch on: run not started`). Check the next `runs.log` shows `wrapper: running production <that commit>`. Then, as `poagent`: `~/po-agent/scripts/macmini-run.sh spike live` (G.5, read only), `~/po-agent/scripts/macmini-run.sh decide-only live` (G.6, books nothing), `~/po-agent/scripts/macmini-run.sh run live` (G.7, `max_notes_per_run = 1`: one watched PO per run). Paste the `runs.log` lines (and for G.7 the `grep <run_id>` trace lines) to the advisor. Each step has its own dated `docs/decisions.md` entry first.

**When the job is loaded (decision D1, 16 Oct 2026):** after the S1 spike (M1), unload it (`launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent`) and check `launchctl print` no longer finds it. Load it again only for the first bookings (plan task 4.6, unloaded again afterwards) and from M6 on. Until then a merge to `main` can't start a booking run, because nothing is scheduled; and since task 7.4 a merge doesn't change the code the job runs until the `production` tag moves.

**On the Mac Mini, one run by hand at a time:** B1's job (:07) and Summit's (:30) share the checkout `~/po-agent`, and each run is stopped at 20 minutes, so scheduled runs never overlap. Before any run by hand, as `poagent`, `pgrep -fl macmini-run.sh` must print nothing; never within a few minutes of :07 or :30.

**One agent at a time:** one laptop test-site run at a time (seam-2 tests, `run`, `spike`): the cross-worktree lock keeps seam-2 pytest runs apart, and no laptop `run` or `spike` starts while another test-site run is going (the lock doesn't cover them); no manual Mac Mini test-site run while a laptop run is going. The Mac Mini's live job keeps running: it uses another site, account and secrets (Joey, 20 Nov 2026; decisions, 20 Nov 2026, one Send Email control).

## 9. Check it worked

`tail -50 ~/Library/Logs/po-agent/runs.log`. A clean `launchctl` state only means the job started.

**The safe trace** (7.3): every run also writes `~/Library/Logs/po-agent/trace/<YYYY-MM-DD>.jsonl` (Perth date), allowlisted fields only (run_id, time, Note ID, step, check or control name, outcome, duration; no page text). Files older than 90 days are deleted at the next run start. Read it after an alert: `grep <run_id> ~/Library/Logs/po-agent/trace/<date>.jsonl`.

| Check | Healthy |
|---|---|
| Fetch and sync | No git or `uv sync` errors in `launchd.log`; `runs.log` shows `wrapper: running production <commit>`, the commit you tagged |
| The run | Ends with one `RUN_SUMMARY {…}` line with `"exit_code": 0`; no PDF text or addresses in the log |
| Alerts | If any `ALERT` line or non-zero exit: an issue labelled `po-agent-alert` exists, and GitHub emailed you |
| Heartbeat | The `po-agent-heartbeat` issue's body shows the last run's time and exit code; no `wrapper: heartbeat not sent` in `runs.log` |
| Healthchecks.io | The check's page shows **up** and a last ping at the run's end; no `wrapper: healthchecks ping not configured` or `not sent` in `runs.log` |
| Schedule | On a weekday, a `RUN_SUMMARY` at about 07:07, 08:07 … 17:07 and none outside; from S.5, also one with `"client": "summit"` at about 07:30 … 17:30 |

There is **no state between runs** in the MVP (`SPEC.md` assumption 5): the agent reads nothing from earlier runs. `runs.log` is only the record for Joey; copy the `RUN_SUMMARY` and `NOTE` lines you need for the CEO note from it.

## 10. After a restart

After a power cut, a macOS update or any restart, the Mac Mini powers back on and **waits at the FileVault unlock screen**. Nothing runs until someone logs in as `poagent`:

1. At the Mac, unlock with the **`poagent`** account (not an admin account), so its session and Keychain open and the job is loaded.
2. Lock the screen: Control-Command-Q. The session keeps running while locked. (System Settings → Lock Screen: require the password **immediately** after the display turns off.)
3. Check the next run appears in `runs.log`: as `poagent`, after the next :07, `tail -20 ~/Library/Logs/po-agent/runs.log` shows a new `RUN_SUMMARY` line.

**Only `poagent` stays logged in** (decisions, 19 Nov 2026, Mac Mini outage). On 18-19 Nov 2026 a macOS update restarted the Mac, the admin account stayed logged in afterwards, and the screen lock logged `poagent` out: no run for about 15 working hours. So:

- An admin who logs in at the Mac (to install an update or change a setting) **logs out** before leaving (Apple menu → Log Out), never just switches users or locks the screen with the admin session still open. Then unlock as `poagent` and lock the screen (steps 1-3).
- After installing a **macOS update** (section 5): the Mac restarts into the FileVault screen; unlock as `poagent`, lock the screen, and check the next run. Also check section 5's Automatic updates settings are still off: an update can change them.
- To check from the admin account who is logged in: `who` lists the sessions; `poagent` must be one of them, on `console`.

Missed runs only delay POs: the Notes stay in the pool, where the admin can handle them. If nobody logs in, the Healthchecks.io check (section 8) emails Joey within about an hour of the first missed run; the backup missed-heartbeat check emails him once 2 hours inside the schedule pass without a run, at its next run: about that weekday afternoon, or the next weekday afternoon if the runs stopped after that day's check. The steps for either alert: `docs/ops-runbook.md`, "`poagent` logged out, or an admin session left on".

## 11. Stop it

Any one of these stops the agent:

1. Set `enabled = false` in the site's config on `main` (`config/live.toml` after go-live, `config/test.toml` for test runs; through a PR). The next run reads it from `origin/main` and runs nothing (`wrapper: enabled = false on main, agent not run`), whichever commit the `production` tag is on. Works from anywhere, once the kill switch is built (plan task 3.5); until then, use 2.
2. On the Mac (or over Remote Login), as an admin: `sudo launchctl bootout gui/$(id -u poagent)/au.com.prompteng.po-agent`, or as `poagent`: `launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent`. No more runs until it's bootstrapped again.

Both stop Summit too (step 1 through `config/live.toml`); to stop **Summit alone**, see section 13.

After an `ALERT ACCURACY_BREACH`, do both, and restart only with the CEO's agreement (approved safeguard). After an `ALERT PARTIAL_WRITE`, the Note stays assigned to the agent: finish Hold, Link and Solved by hand on the test site, then reassign nothing. While a Pending Note is still assigned to the agent, **every run stops at the start** with an `ALERT` and takes no Note (the stale-Note stop, decision D6), so one bug can't leave a half-booked Note every hour. Once the Note is Solved (or moved off the agent), runs resume.

## 12. At the end of the trial

- Unload the job (section 11, step 2).
- Ask the MySys admin to change the test agent account's password. Delete the two test items from `poagent`'s Keychain (`uv run keyring del po-agent <name>`).
- Close the `po-agent-alert` issues once the CEO has reviewed the MVP demo note.
- Production on this Mac Mini (roadmap phase 4) starts only after the CEO's go-live sign-off: live credentials go into the same Keychain then, never earlier.

## 13. Summit Home (client 2): go-live steps S.1-S.5

Summit runs as its own run beside B1's (`SPEC.md` -> Client 2, The separate run): MySys account **Agent 2 (Summit Homes)**, its own Keychain items, kill switch (`enabled` in `config/clients/summit.toml`, with the site's), run lock, launchd job `au.com.prompteng.po-agent.summit` at **30 past** each hour (07:30-17:30 Monday-Friday Perth; Joey, 24 Nov 2026) and Healthchecks.io check. B1's job, schedule and checks don't change.

**Joey only, at the Mac as `poagent`** (zsh), in this order, each step with its own dated `docs/decisions.md` entry first; Claude never runs any of them (CLAUDE.md Must never #3). Before every run by hand: `pgrep -fl macmini-run.sh` prints nothing, and it is not within a few minutes of :07 or :30. Until S.5 every Summit run logs `wrapper: healthchecks ping not configured`: expected.

**S.1 - secrets and pre-flight.** On the laptop first: move the `production` tag to a commit on `main` that holds tasks 9.1-9.15 (section 8, "Moving the production tag", with Claude's release summary), and watch the next B1 run on it. Then at the Mac, check the checkout is on that commit, then store Agent 2's pair (each command prompts; type the value, never paste it into a chat or a file) and check it:

```bash
grep 'wrapper: running production' ~/Library/Logs/po-agent/runs.log | tail -1
cd ~/po-agent && git rev-parse --short=12 HEAD
uv run keyring set po-agent mysys_live_summit_username
uv run keyring set po-agent mysys_live_summit_password
uv run po-agent preflight --site live --client summit
```

Healthy: the two commits match; exit 0 and `INFO  preflight: secrets ok`. If macOS asks for Keychain access, **Always Allow**. Then in MySys (your own login): Note Pool, Assigned User = Agent 2 (Summit Homes), Status Pending lists nothing. Tell the team that from now on nobody assigns a Note to Agent 2 by hand (it would stop every Summit run).

**S.2 - kill switch on, spike.** A PR flips `enabled = false` to `true` in `config/clients/summit.toml` (its own PR, with a `test:` commit and a decisions entry); move the `production` tag to its merge commit. **From that merge, `run live summit` books.** Booking waits for S.4: until then run only `spike` and `decide-only`, and don't load Summit's job until S.5. Then:

```bash
pgrep -fl macmini-run.sh
~/po-agent/scripts/macmini-run.sh spike live summit
tail -30 ~/Library/Logs/po-agent/runs.log
```

Healthy: the first line `=== ... macmini-run.sh spike live summit ===`, `wrapper: running production <the merge commit>`, a `RUN_SUMMARY` with `"client": "summit"` and `"exit_code": 0`, the eligible count, no `MORE_PAGES`. The first Summit run downloads its own Chromium (about a minute; `~/Library/Caches/ms-playwright-summit`).

**S.3 - decide-only.** Books nothing; opens Notes only to read them:

```bash
pgrep -fl macmini-run.sh
~/po-agent/scripts/macmini-run.sh decide-only live summit
tail -40 ~/Library/Logs/po-agent/runs.log
```

Read every `NOTE` line against its Note in MySys; open one peeked Note's log: no new line, the same assignee. The run's length sets `max_peeks_per_run` (its own PR if it changes).

**S.4 - one booking, watched.** First tell the admins that the agent may take a Summit Note from them and gives it back if it stops before Submit. Then, with `max_notes_per_run = 1`:

```bash
pgrep -fl macmini-run.sh
~/po-agent/scripts/macmini-run.sh run live summit
tail -40 ~/Library/Logs/po-agent/runs.log
grep '<run_id>' ~/Library/Logs/po-agent/trace/$(date +%F).jsonl
```

Put the run's `run_id` from its `RUN_SUMMARY` in the `grep`, and check 5.2's trace rule on it (`SPEC.md` -> Production, gate 5). In MySys check the booked task: Creator, PO Number, Documents, Note, On Hold, the Note linked and Solved.

**S.5 - hourly.** In Healthchecks.io (as section 1): **Add Check** `po-agent summit`, **Cron** `30 7-17 * * 1-5`, time zone `Australia/Perth`, **grace time 40 minutes**, email to Joey on. Store its ping URL (it prompts twice; never paste it anywhere else) and check it is there:

```bash
security add-generic-password -s po-agent -a healthchecks_ping_url_summit -w
security find-generic-password -s po-agent -a healthchecks_ping_url_summit > /dev/null && echo stored
```

Raise `max_notes_per_run` by its own PR and move the tag to it. The job's :30 schedule is the Mac's own clock, so it must be on Perth time (section 4). Then load Summit's job:

```bash
date +%Z
mkdir -p ~/Library/Logs/po-agent ~/Library/LaunchAgents
cp ~/po-agent/scripts/au.com.prompteng.po-agent.summit.plist ~/Library/LaunchAgents/
plutil -lint ~/Library/LaunchAgents/au.com.prompteng.po-agent.summit.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/au.com.prompteng.po-agent.summit.plist
launchctl print gui/$(id -u)/au.com.prompteng.po-agent.summit | head -30
```

Healthy: `date +%Z` prints `AWST` (anything else: fix the time zone first, section 4, `sudo systemsetup -settimezone Australia/Perth`); `plutil` says `OK`; `launchctl print` shows the job. Watch the first hourly run at the next :30 (`tail -40 ~/Library/Logs/po-agent/runs.log`: exit 0, no `healthchecks ping` line) and the check turning **up**.

**Run Summit now** (it books): `launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent.summit`.

**Stop Summit alone** (B1 keeps running): unload its job, `launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent.summit`, or the PR setting `enabled = false` in `config/clients/summit.toml` on `main`. While it stays stopped, delete its leftover download folders by hand (`docs/ops-runbook.md` 3.1a): B1's runs don't clear Summit's (decisions, 25 Nov 2026, per-client run controls). A Summit Note left with Agent 2 is given back by hand (`docs/ops-runbook.md` 3.4a).

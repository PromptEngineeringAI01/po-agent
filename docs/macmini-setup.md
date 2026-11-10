# Mac Mini setup — PO Agent (office Mac Mini, test site first)

**Version:** 1.3 · 9 Nov 2026 (1.3: release pinning, task 7.4: the wrapper runs the `production` tag, which only Joey moves; `enabled` is read from `origin/main`; how to move the tag and roll back. 1.2: plan freeze, decisions D1, D6 and D7: wrapper mode mapping, no run after a failed pull, process-group kill, stderr dropped; job unloaded after the S1 spike and loaded only for the first bookings and from M6; one agent at a time; the stale-Note stop. 1.1: "This Mac Mini" check for the office's model A3238) · **Owner:** Joey Wu · **Spec:** `SPEC.md` → Trial conditions, Commands · **Decision:** CEO decision 3 (`docs/decisions.md`, 15 Oct 2026; `docs/specs/ADR-002-po-agent-hosting.md`)
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

Nothing installs by itself, so nothing restarts the Mac during run hours. Joey (or the backup admin) installs updates **after 18:00 on a weekday or at the weekend**, at least monthly and within 7 days of a security update, then logs back in as `poagent` and locks the screen (section 10).

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

**Live secrets (G.4; decisions, 10 Nov 2026, live profile).** Joey only, by hand, and only once ADR-002 H2 passes again (Claude and every other AI tool removed from `poagent`). The live agent account has its own pair, which `--site live` reads:

```bash
uv run keyring set po-agent mysys_live_username
uv run keyring set po-agent mysys_live_password
```

Claude never reads, sets or names these values (CLAUDE.md Must never #3 and #5). The live password has no expiry (Joey's look at live, 10 Nov 2026); if the admin changes it, set the new one the same way, then run one live spike at the Mac.

**Keychain trap:** a Keychain item trusts the program that created it. If uv installs a new Python (a new path), macOS shows an "allow access to the keychain" dialog and an unattended run waits for a click. So: keep Python pinned in `.python-version`; after any Python change, run one spike at the Mac as `poagent` (section 8) and click **Always Allow** for each item. The wrapper's 20-minute limit ends a run stuck on that dialog and raises an alert.

## 8. The scheduled job (launchd)

**The wrapper** `scripts/macmini-run.sh <run|spike|decide-only> <test|live>` does, in order. The site is required, with no default (decisions, 10 Nov 2026, live profile); a missing or unknown site, or any other argument, prints the usage message and exits 2 with nothing run. After go-live the job runs `run live` only.

1. **Release pinning** (task 7.4) in `~/po-agent`: `git fetch --force --prune --prune-tags origin` (a moved tag updates, a deleted one disappears); reads `enabled` from `config/<site>.toml` (`config/test.toml` or `config/live.toml`) on `origin/main`; then checks out the commit of the **`production` tag** (detached HEAD) and logs `wrapper: running production <first 12 characters of the commit>` to `runs.log`. So a merge to `main` changes nothing on the Mac Mini until Joey moves the tag, but `enabled = false` on `main` still stops the next run: the wrapper logs `wrapper: enabled = false on main, agent not run`, checks out nothing and exits 0, with no alert issue.
2. `uv sync --locked`, then `uv run playwright install chromium` (a no-op unless Playwright moved in `uv.lock`). Their own output goes to `launchd.log`.
   **If step 1 or 2 fails, the agent doesn't run**, and it never falls back to the code already on disk: a failed fetch, a missing `production` tag, a failed checkout (for example a file edited by hand in `~/po-agent`), the site's config on `origin/main` without exactly one `enabled = true` or `enabled = false` line, or a failed sync or install. The wrapper writes `wrapper: setup failed (<step>), agent not run` to `runs.log` and opens the alert issue (exit code 2).
3. Runs the agent with `--site <site>` and never `--detailed-log`: mode `run` → `uv run po-agent run`, `spike` → `uv run po-agent spike`, `decide-only` → `uv run po-agent run --decide-only`. It has a 20-minute hard limit. macOS has no GNU `timeout` or `setsid`, so the wrapper implements it: bash job control (`set -m`) starts the agent in its own process group, and the wrapper kills the whole group (uv, Python and Playwright's driver; SIGTERM, then SIGKILL 10 seconds later) at the limit, when the agent ends and when the wrapper itself is stopped. Playwright starts Chromium detached, in a group of its own, so the wrapper then also kills every Playwright browser of `poagent` (`pkill -KILL -u <uid> -f ms-playwright/`, logged as `wrapper: leftover Playwright browser killed` when it finds one). Nothing is left to overlap the next run. A run killed at the limit exits 1 and adds `wrapper: agent killed at the 1200s limit` to `runs.log`.
4. Appends the run's stdout (the stdout contract only: no PDF text, addresses or Note bodies) to `~/Library/Logs/po-agent/runs.log`, after a timestamp line per run (`=== <time> macmini-run.sh <mode> <site> ===`). The agent's stderr goes to `/dev/null`: the agent writes nothing there by design, and a crash's text could quote page content.
5. If the run printed an `ALERT` line or exited non-zero: `gh issue create --label po-agent-alert`, titled `po-agent alert <run_id, or "no run_id">`, whose body is only the `ALERT` lines **without any Note ID**, the wrapper's own fixed line (failed setup or time limit) if there is one, and `exit code: <n>`. The repo is public (audit N4; decisions, 9 and 10 Nov 2026): the wrapper cuts the JSON `note_id` key and the detail's `note_id=<id>`, and a line that still names one keeps only `ALERT <KIND>`. **The Note is named in `runs.log`**, which keeps every `ALERT` line whole (just above the run's `RUN_SUMMARY`), and in the safe trace (`grep <run_id>`, section 9; `docs/ops-runbook.md` section 2). The issue is opened with Joey's own token, and GitHub doesn't email you about your own actions, so `.github/workflows/alert-email.yml` has github-actions[bot] post one fixed comment on it ("po-agent alert: see the issue body."), which emails Joey as the issue's author (Joey's choice, 5 Nov 2026). If `gh` fails, `runs.log` gets `wrapper: alert issue not opened`.
6. **The heartbeat ping** (task 7.1), at the end of every run, whatever the exit code: a failed setup, a run killed at the limit and a stopped wrapper ping too. The wrapper finds the one open issue labelled `po-agent-heartbeat` (section 1) and replaces its body with three lines: `last run: <UTC time>`, `exit code: <n>`, `run_id: <run_id, or "none">`. No PO data, no git push, no new secret (the same `gh` token). If the ping fails, `runs.log` gets `wrapper: heartbeat not sent`, and the run's exit code doesn't change. Every `gh` call (the alert issue and the ping) is killed after 60 seconds, so a hung `gh` can't hold the wrapper and make launchd skip the next runs.

**The missed-heartbeat check** is a scheduled GitHub Action (`.github/workflows/heartbeat.yml`, running `scripts/heartbeat_check.py`; Joey's choice, 5 Nov 2026), so it still works when the Mac Mini is off. Every 30 minutes on weekdays (09:07-19:37 Perth) it reads the `last run:` time from the heartbeat issue's body (not its update time, so a comment or label can't pass for a ping) and counts how much of **today's schedule, 07:07-17:30 Perth**, has passed since then (17:30: the 17:07 run's ping, after its 20-minute limit). More than 2 hours opens an issue labelled `po-agent-alert` titled `po-agent heartbeat missed` (GitHub emails Joey). So nothing alerts at night, at the weekend or in the first 2 hours of a day, a normal end of day never alerts, and two missed runs in a row do, even if GitHub runs the check late. One missed run alone (about 2 hours between pings) doesn't. While that issue is open and was opened after the last ping, no second one opens; **close it once runs are back**. An alert left open from an earlier outage doesn't hide a new one. It uses only the workflow's own `GITHUB_TOKEN` (`issues: write`, `contents: read`). GitHub disables scheduled workflows in a repo with no activity for 60 days: if it shows as disabled in the Actions tab, enable it again. To test it by hand: Actions → heartbeat → Run workflow.

**Moving the production tag** (Joey only, by hand, on the laptop; Claude never creates, moves or pushes it). Move it only to a commit on `main` that has passed CI and has run on the test site. The Mac Mini always runs the tag, so try a new commit from the laptop first (with the job unloaded: one agent at a time).

```bash
git fetch origin
git tag -f production <commit>
git push --force origin refs/tags/production
```

The next scheduled run fetches the tag and runs that commit; check its `wrapper: running production <commit>` line in `runs.log`. The wrapper is part of the tagged code too, so a wrapper change also takes effect only once the tag moves (from the run after the one that checks it out). The first time, the tag doesn't exist yet: the same commands create it (`git tag production <commit>`, no `-f` needed).

**Roll back:** the same commands with an earlier commit; `runs.log`'s `wrapper: running production` lines show which commits ran. Never roll back to a commit from before task 7.4: its wrapper runs `git pull`, which fails on the detached HEAD, so every run would alert and run nothing. To stop runs at once instead, use section 11.

It sets its own `PATH` (`~/.local/bin`, `/opt/homebrew/bin`, then the system folders) because launchd starts jobs with a minimal environment, with an optional `MACMINI_RUN_PATH_PREFIX` in front so the wrapper's tests (`tests/test_macmini_wrapper.py`) can use stub commands. The tests also shorten the limit with `MACMINI_RUN_LIMIT_S`; the Mac Mini never sets either.

**The job** is a LaunchAgent in `poagent`'s own session (not a LaunchDaemon: keyring needs the login Keychain, which is only unlocked while `poagent` is logged in). Label `au.com.prompteng.po-agent`; the plist is in the repo as `scripts/au.com.prompteng.po-agent.plist`:

- `ProgramArguments`: `/Users/poagent/po-agent/scripts/macmini-run.sh`, `run`, `live` (after go-live the Mac Mini runs only live; decisions, 10 Nov 2026). Load it only at G.8 (hourly live runs); the watched live runs before that are started by hand (below). **At G.8, copy the plist again** with the `cp` line below before `launchctl bootstrap`: the copy in `~/Library/LaunchAgents/` from the test-site trial still runs `run` with no site, which the wrapper now refuses (usage message, exit 2), so every scheduled run would do nothing.
- `StartCalendarInterval`: one entry per weekday and hour, **Weekday 1–5 × Hour 7–17, Minute 7** (55 entries) → 07:07, 08:07 … 17:07 Monday–Friday, Perth time (the Mac's clock, section 4). Seven minutes past, as before, so a slow start never lands on the hour.
- `StandardOutPath` / `StandardErrorPath`: `/Users/poagent/Library/Logs/po-agent/launchd.log` (the wrapper's own errors; launchd doesn't expand `~`).
- No `RunAtLoad`, no `KeepAlive`.

launchd never starts the job while it is still running, so scheduled runs can't overlap. The agent's own Perth-window check still applies (`run_window` in the site's config).

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

**One agent at a time:** the laptop and the Mac Mini log in as the same agent account, so their checks can't see each other. While the job is loaded, run nothing against the test site from the laptop (seam-2 tests, `run`, `spike`); for a laptop demo, unload the job first and load it again afterwards.

## 9. Check it worked

`tail -50 ~/Library/Logs/po-agent/runs.log`. A clean `launchctl` state only means the job started.

**The safe trace** (7.3): every run also writes `~/Library/Logs/po-agent/trace/<YYYY-MM-DD>.jsonl` (Perth date), allowlisted fields only (run_id, time, Note ID, step, check or control name, outcome, duration; no page text). Files older than 90 days are deleted at the next run start. Read it after an alert: `grep <run_id> ~/Library/Logs/po-agent/trace/<date>.jsonl`.

| Check | Healthy |
|---|---|
| Fetch and sync | No git or `uv sync` errors in `launchd.log`; `runs.log` shows `wrapper: running production <commit>`, the commit you tagged |
| The run | Ends with one `RUN_SUMMARY {…}` line with `"exit_code": 0`; no PDF text or addresses in the log |
| Alerts | If any `ALERT` line or non-zero exit: an issue labelled `po-agent-alert` exists, and GitHub emailed you |
| Heartbeat | The `po-agent-heartbeat` issue's body shows the last run's time and exit code; no `wrapper: heartbeat not sent` in `runs.log` |
| Schedule | On a weekday, a `RUN_SUMMARY` at about 07:07, 08:07 … 17:07 and none outside |

There is **no state between runs** in the MVP (`SPEC.md` assumption 5): the agent reads nothing from earlier runs. `runs.log` is only the record for Joey; copy the `RUN_SUMMARY` and `NOTE` lines you need for the CEO note from it.

## 10. After a restart

After a power cut or any restart, the Mac Mini powers back on and **waits at the FileVault unlock screen**. Nothing runs until someone logs in as `poagent`:

1. At the Mac, unlock with the **`poagent`** account (not an admin account), so its session and Keychain open and the job is loaded.
2. Lock the screen: Control-Command-Q. The session keeps running while locked. (System Settings → Lock Screen: require the password **immediately** after the display turns off.)
3. Check the next run appears in `runs.log`.

Missed runs only delay POs: the Notes stay in the pool, where the admin can handle them. If nobody logs in, the missed-heartbeat check (section 8) emails Joey once 2 hours inside the schedule pass without a run.

## 11. Stop it

Any one of these stops the agent:

1. Set `enabled = false` in the site's config on `main` (`config/live.toml` after go-live, `config/test.toml` for test runs; through a PR). The next run reads it from `origin/main` and runs nothing (`wrapper: enabled = false on main, agent not run`), whichever commit the `production` tag is on. Works from anywhere, once the kill switch is built (plan task 3.5); until then, use 2.
2. On the Mac (or over Remote Login), as an admin: `sudo launchctl bootout gui/$(id -u poagent)/au.com.prompteng.po-agent`, or as `poagent`: `launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent`. No more runs until it's bootstrapped again.

After an `ALERT ACCURACY_BREACH`, do both, and restart only with the CEO's agreement (approved safeguard). After an `ALERT PARTIAL_WRITE`, the Note stays assigned to the agent: finish Hold, Link and Solved by hand on the test site, then reassign nothing. While a Pending Note is still assigned to the agent, **every run stops at the start** with an `ALERT` and takes no Note (the stale-Note stop, decision D6), so one bug can't leave a half-booked Note every hour. Once the Note is Solved (or moved off the agent), runs resume.

## 12. At the end of the trial

- Unload the job (section 11, step 2).
- Ask the MySys admin to change the test agent account's password. Delete the two test items from `poagent`'s Keychain (`uv run keyring del po-agent <name>`).
- Close the `po-agent-alert` issues once the CEO has reviewed the MVP demo note.
- Production on this Mac Mini (roadmap phase 4) starts only after the CEO's go-live sign-off: live credentials go into the same Keychain then, never earlier.

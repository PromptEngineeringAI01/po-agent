# Mac Mini setup — PO Agent (office Mac Mini, test site first)

**Version:** 1.2 · 16 Oct 2026 (1.2: plan freeze, decisions D1, D6 and D7: wrapper mode mapping, no run after a failed pull, process-group kill, stderr dropped; job unloaded after the S1 spike and loaded only for the first bookings and from M6; one agent at a time; the stale-Note stop. 1.1: "This Mac Mini" check for the office's model A3238) · **Owner:** Joey Wu · **Spec:** `SPEC.md` → Trial conditions, Commands · **Decision:** CEO decision 3 (`docs/decisions.md`, 15 Oct 2026; `docs/specs/ADR-002-po-agent-hosting.md`)
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

- [ ] The repo is on GitHub (private) and `main` has M1's code.
- [ ] An Anthropic API key just for this agent: console.anthropic.com → **API keys** → **Create key**, name `po-agent-trial`, with a low monthly spend limit (e.g. US$10).
- [ ] The test-site agent account username and password, and confirmation that it has no MFA (SPEC open question 3).
- [ ] A GitHub label for alerts. On your laptop: `gh label create po-agent-alert --color B60205`
- [ ] A **fine-grained GitHub token** for the Mac Mini: github.com → Settings → Developer settings → Fine-grained tokens → **Generate**. Name `po-agent-macmini`; resource owner `PromptEngineeringAI01`; **only** the `po-agent` repository; permissions **Contents: Read-only**, **Issues: Read and write** (Metadata: Read-only is added automatically); expiry 90 days (diarise the renewal).
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
- Never install Claude Code or any AI tool for `poagent`. No AI session may read its Keychain (ADR-002 gate H2).
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
uv run keyring set po-agent anthropic_api_key
```

They go into `poagent`'s login Keychain (keyring service `po-agent`; names as `SPEC.md` → Secrets). Don't set any `PO_AGENT_*` environment variable on the Mac Mini.

**Keychain trap:** a Keychain item trusts the program that created it. If uv installs a new Python (a new path), macOS shows an "allow access to the keychain" dialog and an unattended run waits for a click. So: keep Python pinned in `.python-version`; after any Python change, run one spike at the Mac as `poagent` (section 8) and click **Always Allow** for each item. The wrapper's 20-minute limit ends a run stuck on that dialog and raises an alert.

## 8. The scheduled job (launchd)

**The wrapper** `scripts/macmini-run.sh <run|spike|decide-only>` (in the repo from M1) does, in order:

1. `git pull --ff-only` on `main` in `~/po-agent`, so `enabled = false` on `main` still stops the next run.
2. `uv sync --locked`, then `uv run playwright install chromium` (a no-op unless Playwright moved in `uv.lock`).
   **If step 1 or 2 fails, the agent doesn't run** (stale code would ignore `enabled = false` on `main`): the wrapper writes a fixed line to `runs.log` and opens the alert issue (exit code 2).
3. Runs the agent with `--site test` and never `--detailed-log`: mode `run` → `uv run po-agent run`, `spike` → `uv run po-agent spike`, `decide-only` → `uv run po-agent run --decide-only`. It has a 20-minute hard limit. macOS has no GNU `timeout`, so the wrapper implements it, starting the agent in its own process group and killing the whole group (Python and Chromium) at the limit, so nothing is left to overlap the next run.
4. Appends the run's stdout (the stdout contract only: no PDF text, addresses or Note bodies) to `~/Library/Logs/po-agent/runs.log`, with a timestamp line per run. The agent's stderr goes to `/dev/null`: the agent writes nothing there by design, and a crash's text could quote page content.
5. If the run printed an `ALERT` line or exited non-zero: `gh issue create --label po-agent-alert`, titled `po-agent alert <run_id, or "no run_id">`, whose body is only the `ALERT` lines and the exit code. GitHub emails Joey.

It sets its own `PATH` (`~/.local/bin`, `/opt/homebrew/bin`) because launchd starts jobs with a minimal environment, with an optional `MACMINI_RUN_PATH_PREFIX` in front so the wrapper's tests can use stub commands.

**The job** is a LaunchAgent in `poagent`'s own session (not a LaunchDaemon: keyring needs the login Keychain, which is only unlocked while `poagent` is logged in). Label `au.com.prompteng.po-agent`; the plist is in the repo as `scripts/au.com.prompteng.po-agent.plist`:

- `ProgramArguments`: `/Users/poagent/po-agent/scripts/macmini-run.sh`, `run`
- `StartCalendarInterval`: one entry per weekday and hour, **Weekday 1–5 × Hour 7–17, Minute 7** (55 entries) → 07:07, 08:07 … 17:07 Monday–Friday, Perth time (the Mac's clock, section 4). Seven minutes past, as before, so a slow start never lands on the hour.
- `StandardOutPath` / `StandardErrorPath`: `/Users/poagent/Library/Logs/po-agent/launchd.log` (the wrapper's own errors; launchd doesn't expand `~`).
- No `RunAtLoad`, no `KeepAlive`.

launchd never starts the job while it is still running, so scheduled runs can't overlap. The agent's own Perth-window check still applies (`run_window` in `config/test.toml`).

As `poagent`:

```bash
mkdir -p ~/Library/Logs/po-agent ~/Library/LaunchAgents
cp ~/po-agent/scripts/au.com.prompteng.po-agent.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/au.com.prompteng.po-agent.plist
launchctl print gui/$(id -u)/au.com.prompteng.po-agent | head -30    # state, last exit code
```

**Run now** (the scheduled `run` mode, immediately): `launchctl kickstart gui/$(id -u)/au.com.prompteng.po-agent`

**Spike (M1) and decide-only (M3):** as `poagent` in Terminal, `~/po-agent/scripts/macmini-run.sh spike` (or `decide-only`). Don't start a manual run within a few minutes of :07.

**When the job is loaded (decision D1, 16 Oct 2026):** after the S1 spike (M1), unload it (`launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent`) and check `launchctl print` no longer finds it. Load it again only for the first bookings (plan task 4.6, unloaded again afterwards) and from M6 on. Until then a merge to `main` can't start a booking run, because nothing is scheduled.

**One agent at a time:** the laptop and the Mac Mini log in as the same agent account, so their checks can't see each other. While the job is loaded, run nothing against the test site from the laptop (seam-2 tests, `run`, `spike`); for a laptop demo, unload the job first and load it again afterwards.

## 9. Check it worked

`tail -50 ~/Library/Logs/po-agent/runs.log`. A clean `launchctl` state only means the job started.

| Check | Healthy |
|---|---|
| Pull and sync | No git or `uv sync` errors in `launchd.log` |
| The run | Ends with one `RUN_SUMMARY {…}` line with `"exit_code": 0`; no PDF text or addresses in the log |
| Alerts | If any `ALERT` line or non-zero exit: an issue labelled `po-agent-alert` exists, and GitHub emailed you |
| Schedule | On a weekday, a `RUN_SUMMARY` at about 07:07, 08:07 … 17:07 and none outside |

There is **no state between runs** in the MVP (`SPEC.md` assumption 5): the agent reads nothing from earlier runs. `runs.log` is only the record for Joey; copy the `RUN_SUMMARY` and `NOTE` lines you need for the CEO note from it.

## 10. After a restart

After a power cut or any restart, the Mac Mini powers back on and **waits at the FileVault unlock screen**. Nothing runs until someone logs in as `poagent`:

1. At the Mac, unlock with the **`poagent`** account (not an admin account), so its session and Keychain open and the job is loaded.
2. Lock the screen: Control-Command-Q. The session keeps running while locked. (System Settings → Lock Screen: require the password **immediately** after the display turns off.)
3. Check the next run appears in `runs.log`.

Missed runs only delay POs: the Notes stay in the pool, where the admin can handle them. During the trial Joey checks `runs.log` each weekday morning; v1 adds a heartbeat.

## 11. Stop it

Any one of these stops the agent:

1. Set `enabled = false` in `config/test.toml` on `main` (through a PR). The next run pulls it and exits before login. Works from anywhere, once the kill switch is built (plan task 3.5); until then, use 2.
2. On the Mac (or over Remote Login), as an admin: `sudo launchctl bootout gui/$(id -u poagent)/au.com.prompteng.po-agent`, or as `poagent`: `launchctl bootout gui/$(id -u)/au.com.prompteng.po-agent`. No more runs until it's bootstrapped again.

After an `ALERT ACCURACY_BREACH`, do both, and restart only with the CEO's agreement (approved safeguard). After an `ALERT PARTIAL_WRITE`, the Note stays assigned to the agent: finish Hold, Link and Solved by hand on the test site, then reassign nothing. While a Pending Note is still assigned to the agent, **every run stops at the start** with an `ALERT` and takes no Note (the stale-Note stop, decision D6), so one bug can't leave a half-booked Note every hour. Once the Note is Solved (or moved off the agent), runs resume.

## 12. At the end of the trial

- Unload the job (section 11, step 2).
- Revoke the `po-agent-trial` Anthropic key. Ask the MySys admin to change the test agent account's password. Delete the three test items from `poagent`'s Keychain (`uv run keyring del po-agent <name>`).
- Close the `po-agent-alert` issues once the CEO has reviewed the MVP demo note.
- Production on this Mac Mini (roadmap phase 4) starts only after the CEO's go-live sign-off: live credentials go into the same Keychain then, never earlier.

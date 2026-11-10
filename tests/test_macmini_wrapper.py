"""Tests for the Mac Mini wrapper `scripts/macmini-run.sh` and its launchd
plist (plan task 1.9; `docs/macmini-setup.md` section 8), its release
pinning (plan task 7.4): it runs the `production` tag, with `enabled` read
from `origin/main`, and the live profile (G.3): the site is a required
argument, `enabled` comes from that site's config, and alert issues carry
no Note ID (audit N4). Nothing here runs the agent: `uv` is a stub.

The wrapper runs under bash (CI on Linux, Git Bash on Windows) with stub
`git`, `uv` and `gh` first on its PATH via MACMINI_RUN_PATH_PREFIX. The stub
`uv` runs a fake agent script for `uv run po-agent ...`. The wrapper is
copied into a temp folder first, so even if a stub were missed, the real
`git`, `uv` and `gh` would run outside any repo and fail.
"""

import itertools
import os
import plistlib
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = ROOT / "scripts" / "macmini-run.sh"
PLIST = ROOT / "scripts" / "au.com.prompteng.po-agent.plist"
BASH = shutil.which("bash")

RUN_ID = "20261105T000700Z-3fa2"
TAG_SHA = "0123456789abcdef0123456789abcdef01234567"
REAL_CONFIG = (ROOT / "config" / "test.toml").read_text()


def live_config() -> str:
    return (ROOT / "config" / "live.toml").read_text()


INFO = "INFO  config loaded"
NOTE = 'NOTE  {"note_id": "1001", "outcome": "skipped", "reason": "NOT_B1"}'
# ALERT lines as the agent prints them: the Note ID is a JSON key and, from
# str(error), part of the detail too (core/errors.py).
ALERT_1 = (
    'ALERT UNEXPECTED_SCREEN {"note_id": "1002", "step": null, '
    '"detail": "Note window did not open (note_id=1002)"}'
)
ALERT_2 = (
    'ALERT GUARD_REFUSAL {"note_id": "1003", "step": "W2", "detail": '
    '"guard refused the action (action=submit_task, step=W2, note_id=1003, '
    'reason=target_ambiguous)"}'
)
ALERT_3 = 'ALERT CONFIG {"note_id": null, "step": null, "detail": "secret not set"}'
# Anything still naming a Note ID after the strip keeps only its kind.
ALERT_ODD = 'ALERT PARTIAL_WRITE {"step": "W3", "detail": "NOTE_ID=1004"}'
STDERR_TEXT = "stderr text that must not be kept"


def summary(exit_code: int) -> str:
    return f'RUN_SUMMARY {{"run_id": "{RUN_ID}", "exit_code": {exit_code}}}'


# `git show` prints STUB_MAIN_CONFIG if set, else main.toml (the real
# config/test.toml): config on origin/main. `git rev-parse` prints TAG_SHA,
# the production tag's commit, unless STUB_TAG_MISSING is set.
STUB_GIT = """#!/bin/bash
echo "git $*" >> "$STUB_DIR/calls"
case "$1" in
  fetch) exit "${STUB_FETCH_EXIT:-0}" ;;
  rev-parse)
    [ -z "${STUB_TAG_MISSING:-}" ] || exit 1
    echo "$STUB_TAG_SHA" ;;
  show)
    [ "${STUB_SHOW_EXIT:-0}" = 0 ] || exit "$STUB_SHOW_EXIT"
    if [ -n "${STUB_MAIN_CONFIG+set}" ]; then
      printf '%s\\n' "$STUB_MAIN_CONFIG"
    else
      cat "$STUB_DIR/main.toml"
    fi ;;
  checkout) exit "${STUB_CHECKOUT_EXIT:-0}" ;;
esac
exit 0
"""
STUB_UV = """#!/bin/bash
echo "uv $*" >> "$STUB_DIR/calls"
if [ "$1" = run ] && [ "$2" = po-agent ]; then
  exec bash "$STUB_DIR/agent.sh"
fi
if [ "$1" = sync ]; then exit "${STUB_SYNC_EXIT:-0}"; fi
if [ "$1" = run ] && [ "$2" = playwright ]; then exit "${STUB_PLAYWRIGHT_EXIT:-0}"; fi
exit 0
"""
# Playwright starts Chromium detached (its own process group), so the group
# kill can't reach it; the wrapper also kills this user's Playwright browsers.
STUB_PKILL = """#!/bin/bash
echo "pkill $*" >> "$STUB_DIR/pkill.calls"
exit 1
"""
# Each `gh <a> <b> ...` call's arguments go to gh.<a>-<b>.args. The heartbeat
# ping (`issue list`, then `issue edit`) fails with STUB_PING_EXIT; `issue
# list` prints STUB_HEARTBEAT_ISSUE (default 7), the open heartbeat issue.
# STUB_GH_HANG makes every call hang (exec, so the kill reaches the sleep).
STUB_GH = """#!/bin/bash
echo "gh $1 $2" >> "$STUB_DIR/calls"
printf '%s\\0' "$@" > "$STUB_DIR/gh.$1-$2.args"
if [ -n "${STUB_GH_HANG:-}" ]; then exec sleep 300; fi
if [ "$2" = list ] || [ "$2" = edit ]; then
  [ "${STUB_PING_EXIT:-0}" = 0 ] || exit "$STUB_PING_EXIT"
fi
if [ "$2" = list ]; then printf '%s\\n' "${STUB_HEARTBEAT_ISSUE-7}"; fi
exit 0
"""
PING_CALLS = ["gh issue list", "gh issue edit"]
FETCH_CALLS = [
    "git fetch --force --prune --prune-tags origin",
    "git show origin/main:config/test.toml",
    "git rev-parse --verify --quiet refs/tags/production^{commit}",
]
SETUP_CALLS = [
    *FETCH_CALLS,
    f"git checkout --quiet --detach {TAG_SHA}",
    "uv sync --locked",
    "uv run playwright install chromium",
]
TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")


def posix(path: Path) -> str:
    """The path as bash sees it (Git Bash on Windows wants /c/...)."""
    if os.name != "nt":
        return str(path)
    return subprocess.run(
        [BASH, "-c", 'cygpath -u "$1"', "_", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def alive(pid: str) -> bool:
    """Whether a process (by bash's pid) still exists."""
    result = subprocess.run([BASH, "-c", f"kill -0 {pid} 2>/dev/null"])
    return result.returncode == 0


class Box:
    """A temp copy of the wrapper with stub commands and a fake HOME."""

    def __init__(self, tmp: Path):
        self.repo = tmp / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy(WRAPPER, self.repo / "scripts" / "macmini-run.sh")
        self.stubs = tmp / "stubs"
        self.stubs.mkdir()
        for name, body in (
            ("git", STUB_GIT),
            ("uv", STUB_UV),
            ("gh", STUB_GH),
            ("pkill", STUB_PKILL),
        ):
            stub = self.stubs / name
            stub.write_text(body, newline="\n")
            stub.chmod(0o755)
        (self.stubs / "main.toml").write_text(REAL_CONFIG, newline="\n")
        # The checkout's own config (an old tag's) still says enabled = true.
        (self.repo / "config").mkdir()
        (self.repo / "config" / "test.toml").write_text(REAL_CONFIG, newline="\n")
        self.home = tmp / "home"
        self.home.mkdir()
        self.env = {
            **os.environ,
            "MACMINI_RUN_PATH_PREFIX": posix(self.stubs),
            "STUB_DIR": posix(self.stubs),
            "STUB_TAG_SHA": TAG_SHA,
            "HOME": posix(self.home),
        }

    def agent(self, lines: list[str], exit_code: int) -> None:
        printed = "".join(f"echo '{line}'\n" for line in lines)
        self.agent_script(f"{printed}echo '{STDERR_TEXT}' >&2\nexit {exit_code}\n")

    def agent_script(self, body: str) -> None:
        (self.stubs / "agent.sh").write_text("#!/bin/bash\n" + body, newline="\n")

    def run(self, *args: str, timeout: float = 60, **env: str):
        script = posix(self.repo / "scripts" / "macmini-run.sh")
        return subprocess.run(
            [BASH, script, *args],
            env={**self.env, **env},
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def calls(self) -> list[str]:
        path = self.stubs / "calls"
        return path.read_text().splitlines() if path.exists() else []

    def gh_args(self, call: str = "issue-create") -> list[str] | None:
        path = self.stubs / f"gh.{call}.args"
        if not path.exists():
            return None
        return path.read_bytes().decode().split("\0")[:-1]

    def runs_log(self) -> str:
        path = self.home / "Library" / "Logs" / "po-agent" / "runs.log"
        return path.read_text() if path.exists() else ""


def issue(args: list[str]) -> tuple[str, str]:
    """(title, body) of a `gh issue create --label po-agent-alert` call."""
    assert args[:2] == ["issue", "create"]
    assert args[args.index("--label") + 1] == "po-agent-alert"
    return args[args.index("--title") + 1], args[args.index("--body") + 1]


pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")


@pytest.fixture
def box(tmp_path) -> Box:
    return Box(tmp_path)


def test_clean_run_logs_stdout_and_opens_no_issue(box):
    box.agent([INFO, NOTE, summary(0)], 0)

    result = box.run("run", "test")

    assert result.returncode == 0
    assert box.gh_args() is None
    assert box.calls() == [
        *SETUP_CALLS,
        "uv run po-agent run --site test",
        *PING_CALLS,
    ]
    log = box.runs_log()
    assert all(line in log for line in (INFO, NOTE, summary(0)))
    assert f"wrapper: running production {TAG_SHA[:12]}" in log.splitlines()
    assert STDERR_TEXT not in log
    assert log.splitlines()[0] not in (INFO, NOTE, summary(0))  # timestamp line


@pytest.mark.parametrize(
    ("mode", "agent_call"),
    (
        ("spike", "uv run po-agent spike --site test"),
        ("decide-only", "uv run po-agent run --decide-only --site test"),
    ),
)
def test_modes_map_to_the_cli(box, mode, agent_call):
    box.agent([summary(0)], 0)

    result = box.run(mode, "test")

    assert result.returncode == 0
    assert box.calls()[-3:] == [agent_call, *PING_CALLS]


@pytest.mark.parametrize(
    "args",
    (
        ("run",),  # the site is required: no default (decisions, 10 Nov 2026)
        ("run", "staging"),
        ("run", "LIVE"),
        ("run", ""),
        ("run", "test", "extra"),
        ("demo", "test"),
        ("demo", "live"),
        ("",),
        (),
        ("run", "--detailed-log"),
        ("run", "test", "--detailed-log"),
    ),
)
def test_other_arguments_run_nothing(box, args):
    box.agent([summary(0)], 0)

    result = box.run(*args)

    assert result.returncode == 2
    assert box.calls() == []


def test_alert_run_opens_an_issue_with_only_the_alert_lines(box):
    box.agent([INFO, ALERT_1, NOTE, ALERT_2, ALERT_3, ALERT_ODD, summary(1)], 1)

    result = box.run("run", "test")

    assert result.returncode == 1
    title, body = issue(box.gh_args())
    assert title == f"po-agent alert {RUN_ID}"
    # The repo is public: no Note ID in the issue (audit N4; decisions,
    # 9 Nov 2026, go-live plan, item 3).
    assert body.splitlines() == [
        'ALERT UNEXPECTED_SCREEN {"step": null, "detail": "Note window did not open"}',
        'ALERT GUARD_REFUSAL {"step": "W2", "detail": "guard refused the action '
        '(action=submit_task, step=W2, reason=target_ambiguous)"}',
        'ALERT CONFIG {"step": null, "detail": "secret not set"}',
        "ALERT PARTIAL_WRITE",
        "exit code: 1",
    ]
    assert not re.search(r"(?i)note_id|100[234]", body)
    # runs.log on the Mac Mini keeps every ALERT line whole.
    log = box.runs_log().splitlines()
    assert all(line in log for line in (ALERT_1, ALERT_2, ALERT_3, ALERT_ODD))


def test_nonzero_exit_without_alert_opens_an_issue(box):
    box.agent([INFO], 2)

    result = box.run("run", "test")

    assert result.returncode == 2
    title, body = issue(box.gh_args())
    assert title == "po-agent alert no run_id"
    assert body.splitlines() == ["exit code: 2"]


@pytest.mark.parametrize(
    ("failing", "step"),
    (
        ({"STUB_FETCH_EXIT": "1"}, "git fetch"),
        ({"STUB_TAG_MISSING": "1"}, "production tag missing"),
        ({"STUB_SHOW_EXIT": "128"}, "enabled on main"),
        ({"STUB_MAIN_CONFIG": 'site = "test"'}, "enabled on main"),
        ({"STUB_MAIN_CONFIG": "enabled = False"}, "enabled on main"),
        ({"STUB_CHECKOUT_EXIT": "1"}, "git checkout"),
        ({"STUB_SYNC_EXIT": "1"}, "uv sync"),
        ({"STUB_PLAYWRIGHT_EXIT": "1"}, "playwright install"),
    ),
)
def test_failed_setup_runs_no_agent_and_opens_an_issue(box, failing, step):
    box.agent([summary(0)], 0)

    result = box.run("run", "test", **failing)

    assert result.returncode == 2
    assert not any("po-agent" in call for call in box.calls())
    title, body = issue(box.gh_args())
    assert title == "po-agent alert no run_id"
    line = f"wrapper: setup failed ({step}), agent not run"
    assert body.splitlines() == [line, "exit code: 2"]
    assert line in box.runs_log().splitlines()


def test_failed_fetch_or_missing_tag_checks_out_nothing(box):
    # A failed fetch or a missing tag must not fall back to whatever code
    # the checkout already has.
    box.agent([summary(0)], 0)

    for failing in ({"STUB_FETCH_EXIT": "1"}, {"STUB_TAG_MISSING": "1"}):
        (box.stubs / "calls").unlink(missing_ok=True)
        box.run("run", "test", **failing)
        assert not any(
            call.startswith(("git checkout", "git pull", "uv ")) for call in box.calls()
        )


def test_enabled_false_on_main_stops_an_old_tag(box):
    # The production tag's own config says enabled = true; main says false.
    box.agent([summary(0)], 0)
    main_config = REAL_CONFIG.replace("enabled = true", "enabled = false", 1)
    assert main_config != REAL_CONFIG

    result = box.run("run", "test", STUB_MAIN_CONFIG=main_config)

    assert result.returncode == 0
    assert box.calls() == [*FETCH_CALLS[:2], *PING_CALLS]
    assert box.gh_args() is None
    assert (
        "wrapper: enabled = false on main, agent not run" in box.runs_log().splitlines()
    )
    assert ping_body(box)[1:] == ["exit code: 0", "run_id: none"]


@pytest.mark.parametrize(
    ("mode", "agent_call"),
    (
        ("run", "uv run po-agent run --site live"),
        ("decide-only", "uv run po-agent run --decide-only --site live"),
        ("spike", "uv run po-agent spike --site live"),
    ),
)
def test_live_reads_enabled_from_its_own_config_on_main(box, mode, agent_call):
    box.agent([summary(0)], 0)
    live_on = re.sub(r"(?m)^enabled = \w+", "enabled = true", live_config())

    result = box.run(mode, "live", STUB_MAIN_CONFIG=live_on)

    assert result.returncode == 0
    assert box.calls() == [
        FETCH_CALLS[0],
        "git show origin/main:config/live.toml",
        *SETUP_CALLS[2:],
        agent_call,
        *PING_CALLS,
    ]
    assert f"macmini-run.sh {mode} live ===" in box.runs_log().splitlines()[0]


def test_live_as_committed_is_stopped_by_its_kill_switch(box):
    # config/live.toml is committed with enabled = false (Joey, 10 Nov 2026).
    box.agent([summary(0)], 0)

    result = box.run("run", "live", STUB_MAIN_CONFIG=live_config())

    assert result.returncode == 0
    assert box.calls() == [
        FETCH_CALLS[0],
        "git show origin/main:config/live.toml",
        *PING_CALLS,
    ]
    assert box.gh_args() is None
    assert (
        "wrapper: enabled = false on main, agent not run" in box.runs_log().splitlines()
    )


def test_live_without_one_enabled_line_on_main_runs_nothing(box):
    box.agent([summary(0)], 0)
    two_lines = live_config() + "\nenabled = true\n"

    result = box.run("run", "live", STUB_MAIN_CONFIG=two_lines)

    assert result.returncode == 2
    assert not any("po-agent" in call for call in box.calls())
    line = "wrapper: setup failed (enabled on main), agent not run"
    assert line in box.runs_log().splitlines()


def test_wrapper_never_moves_or_pushes_the_tag():
    # Only Joey moves the production tag (plan task 7.4).
    script = WRAPPER.read_text()
    assert not re.search(r"\bgit\s+(tag|push|pull)\b", script)


def test_hung_agent_is_killed_with_its_children(box, tmp_path):
    child_pid = posix(tmp_path / "child.pid")
    box.agent_script(
        f"echo '{INFO}'\nsleep 300 &\necho $! > '{child_pid}'\nsleep 300\n"
    )

    start = time.monotonic()
    result = box.run("run", "test", timeout=60, MACMINI_RUN_LIMIT_S="2")
    elapsed = time.monotonic() - start

    assert elapsed < 30
    assert result.returncode != 0
    pid = (tmp_path / "child.pid").read_text().strip()
    assert not alive(pid)
    title, body = issue(box.gh_args())
    assert title == "po-agent alert no run_id"
    assert INFO not in body
    assert f"exit code: {result.returncode}" in body.splitlines()


def test_hung_agent_also_kills_detached_playwright_browsers(box):
    box.agent_script(f"echo '{INFO}'\nsleep 300\n")

    box.run("run", "test", timeout=60, MACMINI_RUN_LIMIT_S="2")

    calls = (box.stubs / "pkill.calls").read_text().splitlines()
    assert len(calls) >= 1
    args = calls[-1].split()
    assert args[:2] == ["pkill", "-KILL"]
    assert args[args.index("-f") + 1] == "ms-playwright/"
    assert "-u" in args


# 7.1 heartbeat: one ping at the end of every run.


def ping_body(box: Box) -> list[str]:
    """The heartbeat issue's new body, after checking the ping's two calls."""
    gh_issue_calls = [call for call in box.calls() if call.startswith("gh issue")]
    assert gh_issue_calls[-2:] == PING_CALLS
    assert box.calls().count("gh issue edit") == 1
    listed = box.gh_args("issue-list")
    assert listed[listed.index("--label") + 1] == "po-agent-heartbeat"
    assert listed[listed.index("--state") + 1] == "open"
    edit = box.gh_args("issue-edit")
    assert edit[:4] == ["issue", "edit", "7", "--body"]
    assert len(edit) == 5
    return edit[4].splitlines()


@pytest.mark.parametrize("exit_code", (0, 1, 2, 3))
def test_every_exit_code_pings_once(box, exit_code):
    box.agent([INFO, NOTE, summary(exit_code)], exit_code)

    result = box.run("run", "test")

    assert result.returncode == exit_code
    time_line, code_line, run_line = ping_body(box)
    assert TIMESTAMP.fullmatch(time_line.removeprefix("last run: "))
    assert code_line == f"exit code: {exit_code}"
    assert run_line == f"run_id: {RUN_ID}"


def test_failed_git_fetch_still_pings(box):
    box.agent([summary(0)], 0)

    result = box.run("run", "test", STUB_FETCH_EXIT="1")

    assert result.returncode == 2
    assert ping_body(box)[1:] == ["exit code: 2", "run_id: none"]


def test_hung_agent_still_pings(box):
    box.agent_script(f"echo '{INFO}'\nsleep 300\n")

    result = box.run("run", "test", timeout=60, MACMINI_RUN_LIMIT_S="2")

    assert ping_body(box)[1:] == [f"exit code: {result.returncode}", "run_id: none"]


@pytest.mark.parametrize("exit_code", (0, 3))
@pytest.mark.parametrize(
    "failing", ({"STUB_PING_EXIT": "1"}, {"STUB_HEARTBEAT_ISSUE": ""})
)
def test_failed_ping_keeps_the_exit_code(box, exit_code, failing):
    box.agent([summary(exit_code)], exit_code)

    result = box.run("run", "test", **failing)

    assert result.returncode == exit_code
    assert box.gh_args("issue-edit") is None
    assert "wrapper: heartbeat not sent" in box.runs_log().splitlines()


def test_hung_gh_is_killed_and_keeps_the_exit_code(box):
    # A hung gh must not hold the wrapper: launchd skips every later run
    # while it is still running.
    box.agent([INFO], 1)

    start = time.monotonic()
    result = box.run(
        "run", "test", timeout=60, STUB_GH_HANG="1", MACMINI_RUN_GH_LIMIT_S="2"
    )
    elapsed = time.monotonic() - start

    assert elapsed < 30
    assert result.returncode == 1
    log = box.runs_log().splitlines()
    assert "wrapper: alert issue not opened" in log
    assert "wrapper: heartbeat not sent" in log


def test_plist_schedules_55_weekday_runs():
    with PLIST.open("rb") as file:
        plist = plistlib.load(file)

    assert plist["Label"] == "au.com.prompteng.po-agent"
    # After go-live the Mac Mini runs only live (decisions, 10 Nov 2026).
    assert plist["ProgramArguments"] == [
        "/Users/poagent/po-agent/scripts/macmini-run.sh",
        "run",
        "live",
    ]
    entries = plist["StartCalendarInterval"]
    assert len(entries) == 55
    assert all(set(entry) == {"Weekday", "Hour", "Minute"} for entry in entries)
    assert {(e["Weekday"], e["Hour"], e["Minute"]) for e in entries} == set(
        itertools.product(range(1, 6), range(7, 18), (7,))
    )
    for key in ("StandardOutPath", "StandardErrorPath"):
        assert plist[key].startswith("/Users/poagent/Library/Logs/po-agent/")
    assert "RunAtLoad" not in plist
    assert "KeepAlive" not in plist

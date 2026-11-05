"""Tests for the Mac Mini wrapper `scripts/macmini-run.sh` and its launchd
plist (plan task 1.9; `docs/macmini-setup.md` section 8).

The wrapper runs under bash (CI on Linux, Git Bash on Windows) with stub
`git`, `uv` and `gh` first on its PATH via MACMINI_RUN_PATH_PREFIX. The stub
`uv` runs a fake agent script for `uv run po-agent ...`. The wrapper is
copied into a temp folder first, so even if a stub were missed, the real
`git`, `uv` and `gh` would run outside any repo and fail.
"""

import itertools
import os
import plistlib
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
INFO = "INFO  config loaded"
NOTE = 'NOTE  {"note_id": "1001", "outcome": "skipped", "reason": "NOT_B1"}'
ALERT_1 = 'ALERT UNEXPECTED_SCREEN {"note_id": "1002", "step": null, "detail": "fixed"}'
ALERT_2 = 'ALERT GUARD_REFUSAL {"note_id": "1003", "step": "W2", "detail": "fixed"}'
STDERR_TEXT = "stderr text that must not be kept"


def summary(exit_code: int) -> str:
    return f'RUN_SUMMARY {{"run_id": "{RUN_ID}", "exit_code": {exit_code}}}'


STUB_GIT = """#!/bin/bash
echo "git $*" >> "$STUB_DIR/calls"
exit "${STUB_GIT_EXIT:-0}"
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
STUB_GH = """#!/bin/bash
echo "gh" >> "$STUB_DIR/calls"
printf '%s\\0' "$@" > "$STUB_DIR/gh.args"
exit 0
"""


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
        self.home = tmp / "home"
        self.home.mkdir()
        self.env = {
            **os.environ,
            "MACMINI_RUN_PATH_PREFIX": posix(self.stubs),
            "STUB_DIR": posix(self.stubs),
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

    def gh_args(self) -> list[str] | None:
        path = self.stubs / "gh.args"
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

    result = box.run("run")

    assert result.returncode == 0
    assert box.gh_args() is None
    assert box.calls() == [
        "git pull --ff-only",
        "uv sync --locked",
        "uv run playwright install chromium",
        "uv run po-agent run --site test",
    ]
    log = box.runs_log()
    assert all(line in log for line in (INFO, NOTE, summary(0)))
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

    result = box.run(mode)

    assert result.returncode == 0
    assert box.calls()[-1] == agent_call


@pytest.mark.parametrize("args", (("demo",), ("",), (), ("run", "--detailed-log")))
def test_other_arguments_run_nothing(box, args):
    box.agent([summary(0)], 0)

    result = box.run(*args)

    assert result.returncode == 2
    assert box.calls() == []


def test_alert_run_opens_an_issue_with_only_the_alert_lines(box):
    box.agent([INFO, ALERT_1, NOTE, ALERT_2, summary(1)], 1)

    result = box.run("run")

    assert result.returncode == 1
    title, body = issue(box.gh_args())
    assert title == f"po-agent alert {RUN_ID}"
    assert body.splitlines() == [ALERT_1, ALERT_2, "exit code: 1"]


def test_nonzero_exit_without_alert_opens_an_issue(box):
    box.agent([INFO], 2)

    result = box.run("run")

    assert result.returncode == 2
    title, body = issue(box.gh_args())
    assert title == "po-agent alert no run_id"
    assert body.splitlines() == ["exit code: 2"]


@pytest.mark.parametrize(
    "failing",
    (
        {"STUB_GIT_EXIT": "1"},
        {"STUB_SYNC_EXIT": "1"},
        {"STUB_PLAYWRIGHT_EXIT": "1"},
    ),
)
def test_failed_setup_runs_no_agent_and_opens_an_issue(box, failing):
    box.agent([summary(0)], 0)

    result = box.run("run", **failing)

    assert result.returncode == 2
    assert not any("po-agent" in call for call in box.calls())
    title, body = issue(box.gh_args())
    assert title == "po-agent alert no run_id"
    assert "exit code: 2" in body.splitlines()
    assert "agent not run" in box.runs_log()


def test_hung_agent_is_killed_with_its_children(box, tmp_path):
    child_pid = posix(tmp_path / "child.pid")
    box.agent_script(
        f"echo '{INFO}'\nsleep 300 &\necho $! > '{child_pid}'\nsleep 300\n"
    )

    start = time.monotonic()
    result = box.run("run", timeout=60, MACMINI_RUN_LIMIT_S="2")
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

    box.run("run", timeout=60, MACMINI_RUN_LIMIT_S="2")

    calls = (box.stubs / "pkill.calls").read_text().splitlines()
    assert len(calls) >= 1
    args = calls[-1].split()
    assert args[:2] == ["pkill", "-KILL"]
    assert args[args.index("-f") + 1] == "ms-playwright/"
    assert "-u" in args


def test_plist_schedules_55_weekday_runs():
    with PLIST.open("rb") as file:
        plist = plistlib.load(file)

    assert plist["Label"] == "au.com.prompteng.po-agent"
    assert plist["ProgramArguments"] == [
        "/Users/poagent/po-agent/scripts/macmini-run.sh",
        "run",
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

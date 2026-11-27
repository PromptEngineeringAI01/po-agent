"""The one check command (= CI): `uv run scripts/check.py`.

Runs each step in order, stops on the first failure, and prints
"check: all passed" when every step passes:

- default: ruff format --check and ruff check (both --no-cache), mypy, guard
  check, repo data, conflict markers, then the offline tests in parallel
  (pytest-xdist; decisions, 19 Nov 2026). If that run fails and every failed
  test failed on a Playwright TimeoutError (a short page wait under load),
  those tests run once more, serially, and the step passes only if they all
  pass ("rerun after timeout"); any other failure is never rerun (decisions,
  25 Nov 2026, Checkpoint S-A friction decisions).
- `--quick <test paths>`: the same fast steps on the whole repo, then pytest
  on only those paths with the same marker filter, in parallel only past
  QUICK_PARALLEL_MIN selected tests. An inner-loop check, not the gate.
- `--repo-data-only`: just the repo-data rule (the pre-commit hook).

The full check runs one at a time on a machine: it first takes an OS file
lock on `po-agent-check.lock` in the user's temp dir (never the repo, which
differs per worktree), waiting up to CHECK_LOCK_WAIT_S and printing the
holder's PID, worktree and start time, then fails "at check lock" if it is
still held. The OS frees the lock when its holder dies; if the file can't be
opened at all the check runs without it. `--quick` and `--repo-data-only`
take no lock (friction log, 26 Nov 2026; decisions, 27 Nov 2026, friction
rows).

`-n` lives here, never in pyproject `addopts`, so a plain `uv run pytest`
(seam 2 included) stays serial; tests/xdist_guard.py fails any `testsite`
test inside an xdist worker, before its fixtures.
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent
PYTEST_MARKERS = "not live_claude and not testsite and not real_data"
# One worker per CPU, at most 12: on the laptop's 24 logical CPUs, 24 workers
# made the 2 s short page waits time out (decisions, 19 Nov 2026).
PYTEST_PARALLEL = ("-n", "auto", "--maxprocesses", "12", "--dist", "load")
QUICK_PARALLEL_MIN = 50
# xunit1 adds each test's file, so its node id can be rebuilt for a rerun.
JUNIT_FAMILY = ("-o", "junit_family=xunit1")
PLAYWRIGHT_TIMEOUT = re.compile(r"\bplaywright\._impl\._errors\.TimeoutError\b")

# A git conflict: a line starting with exactly 7 of these, then a space or
# the end of the line; "=" counts only between a start and an end.
CONFLICT_START = re.compile(r"<{7}(?: |$)")
CONFLICT_END = re.compile(r">{7}(?: |$)")
CONFLICT_SPLIT = re.compile(r"={7}(?: |$)")

# Everything below is matched lowercased, so any case is caught.
# Folder names that must never be tracked, at any depth (as in .gitignore).
BANNED_DIRS = {
    "private",
    "logs",
    "state",
    ".state",
    "traces",
    ".playwright-cli",
    "secrets",
    ".env",
}
PDF_FIXTURES = "tests/seam1/fixtures/pdfs/"
# File-name patterns banned in any folder.
BANNED_NAMES = {
    "secret file": (".env", ".env.*"),
    "trace or capture file": ("*trace*.zip", "*.har", "*.webm"),
    "image (screen captures are real data)": (
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.webp",
        "*.gif",
    ),
}
LIVE_CONFIG = "config/live*.toml"
# The one committed live config, at the repo root; it holds no secrets
# (decisions, 10 Nov 2026, live profile).
COMMITTED_LIVE_CONFIG = "config/live.toml"

# One full check at a time: three parallel full checks made each other's page
# waits time out (friction log, 26 Nov 2026). A full check takes minutes, so
# half an hour covers a queue of a few; past that the holder is stuck.
CHECK_LOCK_NAME = "po-agent-check.lock"
CHECK_LOCK_WAIT_S = 30 * 60
CHECK_LOCK_POLL_S = 5
# Windows locks one byte far past the holder info, so other processes can
# still read the info; POSIX flock locks the whole file, advisory only (as
# tests/testsite_lock.py and core/runlock.py).
_WINDOWS_LOCK_OFFSET = 2**30

Step = tuple[str, Callable[[], bool]]


def classify(path: str) -> str | None:
    """Why a tracked path breaks the repo-data rule, or None if it's allowed."""
    lower = path.lower()
    parts = lower.split("/")
    for part in parts[:-1]:
        if part in BANNED_DIRS:
            return f"under {part}/"
    if lower.endswith(".pdf") and not lower.startswith(PDF_FIXTURES):
        return f"PDF outside {PDF_FIXTURES}"
    name = parts[-1]
    for reason, patterns in BANNED_NAMES.items():
        for pattern in patterns:
            if fnmatch.fnmatchcase(name, pattern):
                return f"{reason} ({pattern})"
    if path != COMMITTED_LIVE_CONFIG and fnmatch.fnmatchcase(
        "/".join(parts[-2:]), LIVE_CONFIG
    ):
        return f"live config ({LIVE_CONFIG})"
    return None


def tracked(root: Path) -> list[str] | None:
    """The tracked or staged paths, or None if git ls-files fails."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None
    return [path for path in result.stdout.split("\0") if path]


def repo_data_violations(root: Path) -> list[str]:
    """One "<path>: <reason>" line per tracked or staged path that breaks the rule."""
    paths = tracked(root)
    if paths is None:
        return [f"{root}: git ls-files failed (not a git repo?)"]
    violations = []
    for path in paths:
        reason = classify(path)
        if reason:
            violations.append(f"{path}: {reason}")
    return violations


def repo_data() -> bool:
    violations = repo_data_violations(ROOT)
    for line in violations:
        print(f"repo-data: {line}")
    return not violations


def conflict_markers(root: Path) -> list[str]:
    """One "<path>:<line>: conflict marker" per marker line in a tracked text
    file, as it is in the working tree (friction log, 25 Nov 2026)."""
    paths = tracked(root)
    if paths is None:
        return [f"{root}: git ls-files failed (not a git repo?)"]
    found = []
    for path in paths:
        try:
            data = (root / path).read_bytes()
        except OSError:  # deleted in the working tree, or a folder
            continue
        if b"\0" in data:  # binary
            continue
        inside = False
        lines = data.decode("utf-8", "replace").splitlines()
        for number, line in enumerate(lines, 1):
            if CONFLICT_START.match(line):
                inside = True
            elif CONFLICT_END.match(line):
                inside = False
            elif not (inside and CONFLICT_SPLIT.match(line)):
                continue
            found.append(f"{path}:{number}: conflict marker")
    return found


def no_conflict_markers() -> bool:
    found = conflict_markers(ROOT)
    for line in found:
        print(f"conflict-markers: {line}")
    return not found


def command(*args: str) -> Callable[[], bool]:
    def run() -> bool:
        return subprocess.run([sys.executable, "-m", *args], cwd=ROOT).returncode == 0

    return run


def script(path: str) -> Callable[[], bool]:
    def run() -> bool:
        return subprocess.run([sys.executable, path], cwd=ROOT).returncode == 0

    return run


FAST_STEPS: list[Step] = [
    # --no-cache: a stale local cache can't pass what CI fails (friction log,
    # 20 Nov 2026).
    (
        "ruff format --check --no-cache .",
        command("ruff", "format", "--check", "--no-cache", "."),
    ),
    ("ruff check --no-cache .", command("ruff", "check", "--no-cache", ".")),
    ("mypy", command("mypy")),  # files and flags: pyproject [tool.mypy]
    ("guard check", script("scripts/guard_check.py")),
    ("repo data", repo_data),
]


def node_id(case: ElementTree.Element) -> str | None:
    """A junit (xunit1) <testcase>'s pytest node id, or None if its file and
    classname don't fit together."""
    file = (case.get("file") or "").replace("\\", "/")
    classname = case.get("classname") or ""
    name = case.get("name") or ""
    module = file.removesuffix(".py").replace("/", ".")
    if not file.endswith(".py") or not name:
        return None
    if classname == module:
        classes: list[str] = []
    elif classname.startswith(module + "."):
        classes = classname[len(module) + 1 :].split(".")
    else:
        return None
    return "::".join([file, *classes, name])


def failed_tests(report: Path) -> list[tuple[str | None, bool]] | None:
    """(node id, failed on a Playwright TimeoutError) for each failed or
    errored test in a pytest junit report; None if it can't be read."""
    try:
        tree = ElementTree.parse(report)
    except (OSError, ElementTree.ParseError):
        return None
    found: list[tuple[str | None, bool]] = []
    for case in tree.iter("testcase"):
        problems = [child for child in case if child.tag in ("failure", "error")]
        if problems:
            text = "\n".join(
                f"{child.get('message') or ''}\n{child.text or ''}"
                for child in problems
            )
            found.append((node_id(case), bool(PLAYWRIGHT_TIMEOUT.search(text))))
    return found


def rerun_timeouts(failed: list[tuple[str | None, bool]] | None) -> bool:
    """Rerun the failed tests once, serially, only if every one of them failed
    on a Playwright timeout; True only if they all pass then."""
    if not failed:
        print("check: no rerun: the report names no failed test")
        return False
    others = sum(1 for node, timeout in failed if node is None or not timeout)
    if others:
        print(f"check: no rerun: {others} failure(s) are not Playwright timeouts")
        return False
    # In report order, once each (a test can fail its call and its teardown).
    nodes = list(dict.fromkeys(node for node, _ in failed if node is not None))
    print(
        f"check: rerun after timeout: {len(nodes)} test(s) failed on a Playwright"
        " timeout; running them once more, serially:"
    )
    for node in nodes:
        print(f"check:   {node}")
    ok = command("pytest", *nodes, "-m", PYTEST_MARKERS)()
    print(f"check: rerun after timeout {'passed' if ok else 'failed'}")
    return ok


def offline_tests() -> bool:
    with tempfile.TemporaryDirectory() as folder:
        report = Path(folder) / "junit.xml"
        junit = ("--junitxml", str(report), *JUNIT_FAMILY)
        args = ("pytest", "tests", "-m", PYTEST_MARKERS, *PYTEST_PARALLEL, *junit)
        code = subprocess.run([sys.executable, "-m", *args], cwd=ROOT).returncode
        if code == 0:
            return True
        if code != 1:  # interrupted, internal or usage error, or no tests
            return False
        failed = failed_tests(report)
    return rerun_timeouts(failed)


STEPS: list[Step] = [
    *FAST_STEPS,
    ("conflict markers", no_conflict_markers),
    (
        f'pytest tests -m "{PYTEST_MARKERS}" {" ".join(PYTEST_PARALLEL)}',
        offline_tests,
    ),
]


def selected_tests(paths: list[str]) -> int:
    """How many tests `--quick` would run (0 if collection fails: the run
    itself then reports the error)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", PYTEST_MARKERS]
        + paths,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return sum("::" in line for line in result.stdout.splitlines())


def quick_steps(paths: list[str]) -> list[Step]:
    def run_tests() -> bool:
        parallel = selected_tests(paths) > QUICK_PARALLEL_MIN
        extra = PYTEST_PARALLEL if parallel else ()
        return command("pytest", *paths, "-m", PYTEST_MARKERS, *extra)()

    return [
        *FAST_STEPS,
        (
            f'pytest {" ".join(paths)} -m "{PYTEST_MARKERS}"'
            f" (+ {' '.join(PYTEST_PARALLEL)} past {QUICK_PARALLEL_MIN} tests)",
            run_tests,
        ),
    ]


class CheckLockTimeout(Exception):
    """Another full check still held the lock after the wait."""


@dataclass
class CheckLock:
    fd: int

    def release(self) -> None:
        os.ftruncate(self.fd, 0)
        _unlock(self.fd)
        os.close(self.fd)


def check_lock_path() -> Path:
    return Path(tempfile.gettempdir()) / CHECK_LOCK_NAME


def _read_holder(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _holder_text(holder: dict[str, object]) -> str:
    unknown = "unknown"
    return (
        f"PID {holder.get('pid', unknown)}, "
        f"worktree {holder.get('worktree', unknown)}, "
        f"since {holder.get('started', unknown)}"
    )


def take_check_lock(
    path: Path,
    wait_s: float,
    poll_s: float,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> CheckLock | None:
    """Take the lock, waiting up to `wait_s` and printing the holder; raise
    CheckLockTimeout naming the holder after that. None (run unlocked) if
    the lock file can't be opened."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as error:
        print(f"check: running without the check lock ({path}: {error})")
        return None
    start = clock()
    shown: dict[str, object] | None = None
    while True:
        try:
            _lock(fd)
            break
        except OSError:
            holder = _read_holder(path)
            waited = clock() - start
            if waited >= wait_s:
                os.close(fd)
                raise CheckLockTimeout(
                    f"another full check still holds the check lock after "
                    f"{int(waited)} s: {_holder_text(holder)}. Lock file: {path}"
                ) from None
            if holder != shown:
                print(
                    "check: waiting for the check lock (one full check at a time"
                    f" on this machine): {_holder_text(holder)}; giving up after"
                    f" {int(wait_s)} s. Lock file: {path}",
                    flush=True,
                )
                shown = holder
            sleep(min(poll_s, wait_s - waited))
    if shown is not None:
        print(f"check: got the check lock after {int(clock() - start)} s", flush=True)
    info = {
        "pid": os.getpid(),
        "worktree": str(ROOT),
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, json.dumps(info).encode("utf-8"))
    return CheckLock(fd)


if sys.platform == "win32":
    import msvcrt

    def _lock(fd: int) -> None:
        os.lseek(fd, _WINDOWS_LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock(fd: int) -> None:
        os.lseek(fd, _WINDOWS_LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


def full_check() -> int:
    """The gate: every step, one full check at a time on this machine."""
    try:
        lock = take_check_lock(check_lock_path(), CHECK_LOCK_WAIT_S, CHECK_LOCK_POLL_S)
    except CheckLockTimeout as held:
        print(f"check: {held}")
        print("check: failed at check lock")
        return 1
    try:
        return run_checks(STEPS)
    finally:
        if lock is not None:
            lock.release()


def run_checks(steps: list[Step]) -> int:
    for name, run in steps:
        print(f"check: {name}", flush=True)
        if not run():
            print(f"check: failed at {name}")
            return 1
    print("check: all passed")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="The one check command (= CI).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--repo-data-only",
        action="store_true",
        help="run only the repo-data rule on the index (the pre-commit hook)",
    )
    mode.add_argument(
        "--quick",
        nargs="+",
        metavar="TEST_PATH",
        help="ruff, mypy, guard check and repo data on the repo, then pytest on only "
        "these test paths (same marker filter); not the gate",
    )
    args = parser.parse_args(argv)
    if args.repo_data_only:
        sys.exit(run_checks([("repo data", repo_data)]))
    if args.quick:
        sys.exit(run_checks(quick_steps(args.quick)))
    sys.exit(full_check())


if __name__ == "__main__":
    main()

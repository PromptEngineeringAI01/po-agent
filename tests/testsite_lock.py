"""One seam-2 run at a time on this laptop (decisions, 20 Nov 2026).

`testsite` tests log in to the one MySys test site with the one agent
account. tests/xdist_guard.py keeps them out of parallel runs; this lock keeps
two serial runs from two worktrees or sessions apart. It is an OS file lock on
`po-agent-testsite.lock` in the user's temp dir (never the repo, which differs
per worktree):

- a run that selects a `testsite` test takes it once collection and `-m` are
  done, before any fixture, and holds it until pytest exits;
- a second run stops with a usage error naming the holder's PID, worktree and
  start time;
- the OS frees the lock when its process dies, so a crashed run never blocks:
  the next run finds the crashed holder's info still in the file (a clean
  release empties it), marks the new lock `stale` and overwrites it.

The file is never deleted: a run that opened it just before a delete could
lock the old file while another locks a new one. `--collect-only` and xdist
workers (which tests/xdist_guard.py fails) take no lock.

Registered by tests/conftest.py (`pytest_plugins`), where every `testsite`
test lives, not by tests/seam2/conftest.py, which tests/test_seam2_report.py
copies on its own. tests/test_testsite_lock.py checks that and loads it with
`-p testsite_lock` in dummy projects.
"""

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

LOCK_NAME = "po-agent-testsite.lock"
# Windows locks one byte far past the holder info, so other processes can
# still read the info; POSIX flock locks the whole file, advisory only.
_WINDOWS_LOCK_OFFSET = 2**30


class TestsiteLockHeld(Exception):
    """Another seam-2 run holds the test-site lock."""

    __test__ = False  # not a test class, despite the name


@dataclass
class TestsiteLock:
    __test__ = False

    fd: int
    path: Path
    stale: bool = False
    stale_pid: int | None = None

    def release(self) -> None:
        os.ftruncate(self.fd, 0)
        _unlock(self.fd)
        os.close(self.fd)


def default_path() -> Path:
    return Path(tempfile.gettempdir()) / LOCK_NAME


def acquire(path: Path, worktree: str) -> TestsiteLock:
    """Take the lock or raise TestsiteLockHeld naming the holder."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _lock(fd)
    except OSError:
        os.close(fd)
        raise TestsiteLockHeld(_held_message(_read_holder(path), path)) from None
    previous = _read_holder(path)
    holder = {
        "pid": os.getpid(),
        "worktree": worktree,
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, json.dumps(holder).encode("utf-8"))
    pid = previous.get("pid")
    return TestsiteLock(
        fd,
        path,
        stale=bool(previous),
        stale_pid=pid if isinstance(pid, int) else None,
    )


def _read_holder(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _held_message(holder: dict[str, object], path: Path) -> str:
    unknown = "unknown"
    return (
        "seam 2 is already running on this laptop: "
        f"PID {holder.get('pid', unknown)}, "
        f"worktree {holder.get('worktree', unknown)}, "
        f"since {holder.get('started', unknown)}. "
        "Only one test-site run at a time (one agent account, one test site). "
        "Wait for it to finish; the lock frees itself when that process ends. "
        f"Lock file: {path}"
    )


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


_STASH = pytest.StashKey[TestsiteLock]()


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items) -> None:
    # trylast: after `-m` has deselected, so only selected tests count.
    if config.option.collectonly or hasattr(config, "workerinput"):
        return
    if not any(item.get_closest_marker("testsite") for item in items):
        return
    try:
        config.stash[_STASH] = acquire(default_path(), str(config.rootpath))
    except TestsiteLockHeld as held:
        raise pytest.UsageError(str(held)) from None


def pytest_unconfigure(config: pytest.Config) -> None:
    lock = config.stash.get(_STASH, None)
    if lock is not None:
        lock.release()

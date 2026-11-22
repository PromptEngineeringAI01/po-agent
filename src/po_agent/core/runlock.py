"""One run at a time per site (docs/decisions.md, 20 Nov 2026, run lock).

An OS file lock on `state/run-<site>.lock`, taken at the start of every
`po-agent` run (cli._run) and held until the process ends. It keeps a launchd
run and a manual run, or a slow run and the next hour's, from logging in to
one site with its one agent account at once.

- The OS frees the lock when its process dies, however it dies, so a crash or
  a kill never leaves a stale lock and no one has to delete a file.
- A run that finds the lock held does not start (cli prints a fixed INFO
  line, exit 0): that is the normal result of a manual run overlapping
  launchd's. The holder's info (pid, start time) is only read to see how long
  it has held the lock; over `STUCK_AFTER_S` is a stuck run, which cli
  reports as ALERT RUN_LOCK_STUCK. The wrapper's 20-minute limit kills a
  launchd run long before that, so only a hung manual run gets there.
- The file is never deleted: a run that opened it just before a delete could
  lock the old file while another locks a new one.
- The info is not a secret and not PO data: a pid and a timestamp.

Same technique as tests/testsite_lock.py (the seam-2 lock, which lives in the
user's temp dir because tests run from many worktrees): this one lives in the
checkout's `state/`, because the agent runs from one checkout on one machine.
Windows locks one byte far past the info so other processes can still read it;
POSIX flock locks the whole file, advisory only.
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# A holder older than this is stuck, not just busy (a run takes minutes).
STUCK_AFTER_S = 3600
_WINDOWS_LOCK_OFFSET = 2**30


class RunLockHeld(Exception):
    """Another run holds the lock. `held_s` is how long, if its info is
    readable, else None."""

    def __init__(self, held_s: int | None) -> None:
        super().__init__("run lock held")
        self.held_s = held_s


@dataclass
class RunLock:
    fd: int

    def release(self) -> None:
        os.ftruncate(self.fd, 0)
        _unlock(self.fd)
        os.close(self.fd)


def acquire(path: Path, now: datetime | None = None) -> RunLock:
    """Take the lock or raise RunLockHeld. Raises OSError if the file or its
    folder can't be created or opened (the caller fails closed)."""
    now = now or datetime.now(UTC)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _lock(fd)
    except OSError:
        os.close(fd)
        raise RunLockHeld(_held_for(path, now)) from None
    info = {"pid": os.getpid(), "started": now.isoformat(timespec="seconds")}
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, json.dumps(info).encode("utf-8"))
    return RunLock(fd)


def _held_for(path: Path, now: datetime) -> int | None:
    try:
        started = datetime.fromisoformat(json.loads(path.read_text("utf-8"))["started"])
        if started.tzinfo is None:
            return None
        return max(0, int((now - started).total_seconds()))
    except (OSError, ValueError, KeyError, TypeError):
        return None


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

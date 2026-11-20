"""The run lock (docs/decisions.md, 20 Nov 2026, run lock; threat model gap 2).

Two agent runs on one site must never overlap: a launchd run and a manual run,
or a slow run and the next hour's. `core/runlock.py` is an OS file lock on
`state/run-<site>.lock`; the OS frees it when its process dies, so a crash
never leaves a stale lock. A run that finds it held does not start: INFO and
exit 0, no ALERT (a manual run overlapping is normal), unless the holder began
over an hour ago, when it is ALERT RUN_LOCK_STUCK (exit 1).

Every lock file is under tmp_path; nothing here reaches MySys. Values are fake.
"""

import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from po_agent import cli
from po_agent.core import runlock
from po_agent.core.config import CONFIG_DIR

HELD_LINE = "INFO  run lock held: run not started"
NOW = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)

HOLDER = """
import os
import sys
from pathlib import Path
from po_agent.core import runlock
lock = runlock.acquire(Path(sys.argv[1]))
print("held", flush=True)
if sys.stdin.readline().strip() == "crash":
    os._exit(3)
lock.release()
"""


@pytest.fixture
def state(env, tmp_path) -> Path:
    path = tmp_path / "state"
    env.setattr(cli, "STATE_DIR", path, raising=False)
    return path


@pytest.fixture
def killed(env, tmp_path) -> None:
    """The test site's kill switch on: a run that gets past the lock stops at
    once with `kill switch on`, exit 0, with nothing launched."""
    toml = (CONFIG_DIR / "test.toml").read_text("utf-8")
    (tmp_path / "config" / "test.toml").write_text(
        toml.replace("enabled = true", "enabled = false"), "utf-8"
    )


class Holder:
    def __init__(self, path: Path):
        self.proc = subprocess.Popen(
            [sys.executable, "-c", HOLDER, str(path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        assert self.proc.stdout.readline().strip() == "held"

    def finish(self, how: str = "release") -> None:
        self.proc.communicate(how + "\n", timeout=30)


def run_main(capsys, *argv: str) -> tuple[int, list[str]]:
    code = cli.main(list(argv))
    return code, capsys.readouterr().out.splitlines()


def test_second_acquire_is_refused_until_release(tmp_path):
    path = tmp_path / "run-test.lock"
    first = runlock.acquire(path)
    with pytest.raises(runlock.RunLockHeld):
        runlock.acquire(path)
    first.release()
    runlock.acquire(path).release()


def test_held_by_another_process_and_freed_when_it_crashes(tmp_path):
    path = tmp_path / "run-test.lock"
    holder = Holder(path)
    with pytest.raises(runlock.RunLockHeld):
        runlock.acquire(path)
    holder.finish("crash")
    runlock.acquire(path).release()  # the OS freed it: no stale lock


def test_holder_start_time_is_reported(tmp_path):
    path = tmp_path / "run-test.lock"
    lock = runlock.acquire(path, now=NOW - timedelta(minutes=5))
    with pytest.raises(runlock.RunLockHeld) as held:
        runlock.acquire(path, now=NOW)
    assert held.value.held_s == 300
    lock.release()


def test_unreadable_holder_info_gives_no_age(tmp_path):
    path = tmp_path / "run-test.lock"
    lock = runlock.acquire(path)
    path.write_bytes(b"")  # as if the holder's info was never written
    with pytest.raises(runlock.RunLockHeld) as held:
        runlock.acquire(path)
    assert held.value.held_s is None
    lock.release()


def test_run_takes_the_lock_and_frees_it_after(state, killed, capsys):
    code, out = run_main(capsys, "run", "--site", "test")

    assert code == 0
    assert "INFO  kill switch on: run not started" in out
    runlock.acquire(state / "run-test.lock").release()  # freed at the end


def test_held_lock_skips_the_run_cleanly(state, killed, capsys):
    leftover = Path(tempfile.gettempdir()) / "po-agent-dl-someone-elses-run"
    leftover.mkdir()
    lock = runlock.acquire(state / "run-test.lock")

    code, out = run_main(capsys, "run", "--site", "test")

    lock.release()
    assert code == 0
    assert out[0] == HELD_LINE
    assert not any(line.startswith("ALERT") for line in out)
    assert out[-1].startswith("RUN_SUMMARY ")
    assert len(out) == 2  # nothing else ran: no config, no kill-switch line
    assert leftover.exists()  # the sweep, which would delete it, did not run


def test_held_lock_skips_every_mode(state, killed, capsys):
    lock = runlock.acquire(state / "run-test.lock")
    for argv in (
        ("run", "--decide-only", "--site", "test"),
        ("spike", "--site", "test"),
    ):
        code, out = run_main(capsys, *argv)
        assert (code, out[0]) == (0, HELD_LINE)
    lock.release()


def test_lock_held_over_an_hour_is_an_alert(state, killed, capsys):
    started = datetime.now(UTC) - timedelta(hours=2)
    lock = runlock.acquire(state / "run-test.lock", now=started)

    code, out = run_main(capsys, "run", "--site", "test")

    lock.release()
    assert code == 1
    assert out[0].startswith("ALERT RUN_LOCK_STUCK {")
    assert "run lock held" in out[0]
    assert out[-1].startswith("RUN_SUMMARY ")


def test_lock_held_just_under_an_hour_is_not_an_alert(state, killed, capsys):
    started = datetime.now(UTC) - timedelta(minutes=59)
    lock = runlock.acquire(state / "run-test.lock", now=started)

    code, out = run_main(capsys, "run", "--site", "test")

    lock.release()
    assert (code, out[0]) == (0, HELD_LINE)


def test_the_lock_is_per_site(state, killed, capsys):
    lock = runlock.acquire(state / "run-live.lock")  # another site's lock

    code, out = run_main(capsys, "run", "--site", "test")

    lock.release()
    assert code == 0
    assert "INFO  kill switch on: run not started" in out


def test_a_bad_site_takes_no_lock(state, capsys):
    code, out = run_main(capsys, "run", "--site", "nowhere")  # ConfigError

    assert code == 2
    assert any(line.startswith("ALERT CONFIG") for line in out)
    assert not state.exists() or not list(state.iterdir())


def test_lock_file_unavailable_stops_the_run(env, killed, capsys, tmp_path):
    blocker = tmp_path / "state"
    blocker.write_text("a file where the folder should be")
    env.setattr(cli, "STATE_DIR", blocker, raising=False)

    code, out = run_main(capsys, "run", "--site", "test")

    assert code == 2
    assert out[0].startswith("ALERT CONFIG {")
    assert "kill switch" not in "\n".join(out)  # failed closed, ran nothing

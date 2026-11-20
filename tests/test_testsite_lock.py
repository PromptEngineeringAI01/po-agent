"""One seam-2 run at a time on this laptop, across worktrees and sessions.

Two serial `pytest tests/seam2 -m testsite` runs from two worktrees would log
in to the one MySys test site with the one agent account at once. The lock
(tests/testsite_lock.py, hooked into tests/seam2/conftest.py) is an OS file
lock in the user's temp dir: the first run holds it for its session; a second
run stops at collection, naming the holder's PID and worktree. The OS frees
the lock when its process dies, so a crashed run never blocks the next one.

Every run here is a subprocess on a lock file under tmp_path or a dummy test
in tmp_path, so no test reaches MySys.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import testsite_lock

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
HELD_MESSAGE = "seam 2 is already running on this laptop"

HOLDER = """
import os
import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
import testsite_lock
lock = testsite_lock.acquire(Path(sys.argv[2]), sys.argv[3])
print("held", os.getpid(), flush=True)
if sys.stdin.readline().strip() == "crash":
    os._exit(3)
lock.release()
print("released", flush=True)
"""


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONPATH"] = str(TESTS)
    env.update(extra)
    return env


class Holder:
    """A second process that takes the lock and holds it until told."""

    def __init__(self, path: Path, worktree: str, env: dict[str, str] | None = None):
        self.proc = subprocess.Popen(
            [sys.executable, "-c", HOLDER, str(TESTS), str(path), worktree],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env or clean_env(),
        )
        assert self.proc.stdout is not None
        line = self.proc.stdout.readline().split()
        assert line[:1] == ["held"], (
            self.proc.stderr.read() if self.proc.stderr else line
        )
        # The holder's own PID: on Windows a venv's python.exe is a launcher,
        # so Popen.pid is the launcher's, not the process holding the lock.
        self.pid = int(line[1])

    def finish(self, command: str = "release") -> int:
        assert self.proc.stdin is not None
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()
        return self.proc.wait(timeout=30)


@pytest.fixture
def holders():
    started: list[Holder] = []

    def start(path: Path, worktree: str, env: dict[str, str] | None = None):
        holder = Holder(path, worktree, env)
        started.append(holder)
        return holder

    yield start
    for holder in started:
        if holder.proc.poll() is None:
            holder.proc.kill()
            holder.proc.wait(timeout=30)


def test_a_second_process_is_refused_naming_the_holder(tmp_path, holders):
    path = tmp_path / "seam2.lock"
    holder = holders(path, "C:/fake/worktree-a")

    with pytest.raises(testsite_lock.TestsiteLockHeld) as refused:
        testsite_lock.acquire(path, "C:/fake/worktree-b")

    message = str(refused.value)
    assert HELD_MESSAGE in message
    assert f"PID {holder.pid}" in message
    assert "C:/fake/worktree-a" in message
    assert holder.finish() == 0


def test_the_lock_is_free_again_once_the_holder_releases(tmp_path, holders):
    path = tmp_path / "seam2.lock"
    holders(path, "C:/fake/worktree-a").finish()

    lock = testsite_lock.acquire(path, "C:/fake/worktree-b")
    try:
        assert not lock.stale
        holder = json.loads(path.read_text("utf-8"))
        assert holder["pid"] == os.getpid()
        assert holder["worktree"] == "C:/fake/worktree-b"
    finally:
        lock.release()


def test_a_crashed_holder_is_detected_and_cleared(tmp_path, holders):
    path = tmp_path / "seam2.lock"
    holder = holders(path, "C:/fake/worktree-a")
    crashed_pid = holder.pid
    assert holder.finish("crash") == 3  # no release: the holder info stays

    lock = testsite_lock.acquire(path, "C:/fake/worktree-b")
    try:
        assert lock.stale
        assert lock.stale_pid == crashed_pid
        assert json.loads(path.read_text("utf-8"))["pid"] == os.getpid()
    finally:
        lock.release()


def test_the_default_lock_lives_in_the_user_temp_dir_not_the_repo():
    path = testsite_lock.default_path()

    assert path.parent.resolve() == Path(__import__("tempfile").gettempdir()).resolve()
    assert not path.resolve().is_relative_to(ROOT)


def dummy_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    (project / "pytest.ini").write_text(
        "[pytest]\naddopts = --strict-markers\nmarkers =\n    testsite: fake\n",
        encoding="utf-8",
    )
    (project / "test_dummy.py").write_text(
        "import pytest\n\n\n"
        "@pytest.mark.testsite\n"
        "def test_marked():\n    pass\n\n\n"
        "def test_plain():\n    pass\n",
        encoding="utf-8",
    )
    return project


def temp_env(tmp_path: Path) -> dict[str, str]:
    temp = tmp_path / "temp"
    temp.mkdir(exist_ok=True)
    return clean_env(TMP=str(temp), TEMP=str(temp), TMPDIR=str(temp))


def run_pytest(*args: str, cwd: Path, env: dict[str, str]):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )


def held_by_another_run(tmp_path: Path, holders) -> tuple[Holder, dict[str, str]]:
    env = temp_env(tmp_path)
    path = tmp_path / "temp" / testsite_lock.LOCK_NAME
    return holders(path, "C:/fake/other-worktree", env), env


def test_a_testsite_run_stops_at_collection_while_another_holds_it(tmp_path, holders):
    holder, env = held_by_another_run(tmp_path, holders)

    result = run_pytest(
        "-p", "testsite_lock", "-m", "testsite", cwd=dummy_project(tmp_path), env=env
    )

    out = result.stdout + result.stderr
    assert result.returncode != 0
    assert HELD_MESSAGE in out
    assert f"PID {holder.pid}" in out
    assert "C:/fake/other-worktree" in out
    assert "passed" not in out


def test_a_testsite_run_takes_the_lock_when_free(tmp_path):
    env = temp_env(tmp_path)

    result = run_pytest(
        "-p", "testsite_lock", "-m", "testsite", cwd=dummy_project(tmp_path), env=env
    )

    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "1 passed" in out
    assert (tmp_path / "temp" / testsite_lock.LOCK_NAME).exists()


@pytest.mark.parametrize(
    "args",
    [("-m", "not testsite"), ("-m", "testsite", "--collect-only")],
    ids=["testsite-deselected", "collect-only"],
)
def test_runs_that_log_in_nowhere_ignore_the_lock(tmp_path, holders, args):
    _, env = held_by_another_run(tmp_path, holders)

    result = run_pytest(
        "-p", "testsite_lock", *args, cwd=dummy_project(tmp_path), env=env
    )

    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert HELD_MESSAGE not in out


def test_the_seam2_conftest_takes_and_releases_the_lock():
    # In process, never a seam-2 run: load the conftest module by path.
    spec = importlib.util.spec_from_file_location(
        "seam2_conftest_under_test", TESTS / "seam2" / "conftest.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert (
        module.pytest_collection_modifyitems
        is testsite_lock.pytest_collection_modifyitems
    )
    assert module.pytest_unconfigure is testsite_lock.pytest_unconfigure

"""Tests for scripts/check.py: the repo-data rule and the check command's steps."""

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYTEST_MARKERS = "not live_claude and not testsite and not real_data"
# The offline tests run in parallel (decisions, 19 Nov 2026, pytest-xdist).
PARALLEL = ["-n", "auto", "--maxprocesses", "12", "--dist", "load"]


@pytest.fixture(scope="module")
def check_script():
    # scripts/ isn't a package, so load the file directly.
    spec = importlib.util.spec_from_file_location(
        "check_script", ROOT / "scripts" / "check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def no_outer_git_env(monkeypatch):
    # Inside a git hook, git sets these for the outer repo. Without this, the
    # temp repos' `git add` would stage fake files into this repo's index.
    for name in (
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_WORK_TREE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
    ):
        monkeypatch.delenv(name, raising=False)


def make_repo(root: Path, staged: list[str], unstaged: tuple[str, ...] = ()) -> Path:
    """A temp git repo with `staged` files in the index (no commit needed)."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for rel in [*staged, *unstaged]:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    if staged:
        subprocess.run(["git", "-C", str(root), "add", "--", *staged], check=True)
    return root


CLEAN = [
    "README.md",
    "src/x.py",
    "src/po_agent/core/secrets.py",
    "config/test.toml",
    ".github/workflows/check.yml",
    ".pre-commit-config.yaml",
    "docs/screen-map/row02.yml",
    "tests/seam1/fixtures/pdfs/a.pdf",
    "tests/seam1/fixtures/pdfs/sub/B.PDF",
]


def test_clean_repo_has_no_violations(tmp_path, check_script):
    repo = make_repo(tmp_path, CLEAN)
    assert check_script.repo_data_violations(repo) == []


@pytest.mark.parametrize(
    "bad",
    [
        # banned folders, at any depth, any case
        "private/notes.txt",
        "Private/notes.txt",
        "LOGS/run.jsonl",
        "src/Traces/x.py",
        "logs/run.jsonl",
        "state/s.json",
        ".playwright-cli/snap.yml",
        ".state/s.json",
        "traces/run.json",
        "src/state/x.py",
        "src/.state/x.py",
        "src/traces/x.py",
        # PDFs outside the fixtures folder
        "po.pdf",
        "docs/PO.Pdf",
        "tests/seam1/fixtures/a.pdf",
        # traces and captures, any case
        "trace.zip",
        "TRACE.ZIP",
        "out/run.trace.zip",
        "net.har",
        "rec.webm",
        "net.HAR",
        # secret files, at any depth, any case; no .env.example exception
        ".env",
        ".env.local",
        ".env.example",
        "config/.ENV",
        ".env/key.txt",
        "src/.ENV/key.txt",
        "secrets/key.txt",
        "src/Secrets/key.txt",
        # config/live.toml is the one live config (decisions, 10 Nov 2026)
        "config/Live-prod.TOML",
        "config/live.local.toml",
        "deploy/config/live.toml",
        # images anywhere (screen captures are real data)
        "docs/screen-map/row02.png",
        "shot.PNG",
        "a.jpg",
        "b.JPEG",
        "c.webp",
        "d.gif",
    ],
)
def test_each_bad_path_is_named(tmp_path, check_script, bad):
    repo = make_repo(tmp_path, [*CLEAN, bad])
    violations = check_script.repo_data_violations(repo)
    assert len(violations) == 1
    assert violations[0].startswith(f"{bad}: ")


def test_the_committed_live_config_is_allowed(tmp_path, check_script):
    # It holds no secrets (decisions, 10 Nov 2026, live profile).
    repo = make_repo(tmp_path, [*CLEAN, "config/live.toml"])
    assert check_script.repo_data_violations(repo) == []


def test_untracked_files_are_ignored(tmp_path, check_script):
    repo = make_repo(tmp_path, CLEAN, unstaged=("private/x.pdf", "logs/run.jsonl"))
    assert check_script.repo_data_violations(repo) == []


def test_not_a_git_repo_is_a_violation(tmp_path, check_script):
    assert check_script.repo_data_violations(tmp_path) != []


def test_run_checks_stops_at_first_failure(capsys, check_script):
    called = []

    def step(name, ok):
        def run():
            called.append(name)
            return ok

        return (name, run)

    code = check_script.run_checks([step("a", True), step("b", False), step("c", True)])

    out = capsys.readouterr().out
    assert code != 0
    assert called == ["a", "b"]
    assert "check: failed at b" in out
    assert "check: all passed" not in out


def test_run_checks_all_passed(capsys, check_script):
    code = check_script.run_checks([("a", lambda: True), ("b", lambda: True)])

    out = capsys.readouterr().out
    assert code == 0
    assert out.strip().splitlines()[-1] == "check: all passed"


def test_steps_are_in_spec_order(check_script):
    names = [name for name, _ in check_script.STEPS]
    assert names == [
        "ruff format --check --no-cache .",
        "ruff check --no-cache .",
        "mypy",
        "guard check",
        "repo data",
        "conflict markers",
        f'pytest tests -m "{PYTEST_MARKERS}" {" ".join(PARALLEL)}',
    ]


def test_steps_run_the_spec_commands(monkeypatch, check_script):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs.get("cwd")))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(check_script.subprocess, "run", fake_run)
    in_process = ("repo data", "conflict markers")
    command_steps = [run for name, run in check_script.STEPS if name not in in_process]
    for run in command_steps:
        assert run() is True

    python_m = [sys.executable, "-m"]
    assert calls[:-1] == [
        (
            [*python_m, "ruff", "format", "--check", "--no-cache", "."],
            check_script.ROOT,
        ),
        ([*python_m, "ruff", "check", "--no-cache", "."], check_script.ROOT),
        ([*python_m, "mypy"], check_script.ROOT),
        ([sys.executable, "scripts/guard_check.py"], check_script.ROOT),
    ]
    # The offline tests also write a junit report, read only after a failure
    # (decisions, 25 Nov 2026, Checkpoint S-A friction decisions).
    args, cwd = calls[-1]
    assert cwd == check_script.ROOT
    assert args[:-4] == [*python_m, "pytest", "tests", "-m", PYTEST_MARKERS, *PARALLEL]
    assert args[-4] == "--junitxml"
    assert args[-2:] == ["-o", "junit_family=xunit1"]


def test_command_step_fails_on_nonzero_exit(monkeypatch, check_script):
    monkeypatch.setattr(
        check_script.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1),
    )
    _, ruff_format = check_script.STEPS[0]
    assert ruff_format() is False


def test_repo_data_step_fails_and_names_the_path(
    tmp_path, monkeypatch, capsys, check_script
):
    repo = make_repo(tmp_path, [*CLEAN, "private/notes.txt"])
    monkeypatch.setattr(check_script, "ROOT", repo)
    repo_data = dict(check_script.STEPS)["repo data"]

    assert repo_data() is False
    assert "repo-data: private/notes.txt: " in capsys.readouterr().out


def test_repo_data_step_passes_on_a_clean_repo(
    tmp_path, monkeypatch, capsys, check_script
):
    repo = make_repo(tmp_path, CLEAN)
    monkeypatch.setattr(check_script, "ROOT", repo)
    repo_data = dict(check_script.STEPS)["repo data"]

    assert repo_data() is True
    assert "repo-data:" not in capsys.readouterr().out


def test_project_config():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["scripts"]["po-agent"] == "po_agent.cli:main"
    pytest_opts = pyproject["tool"]["pytest"]["ini_options"]
    assert "--strict-markers" in pytest_opts["addopts"]
    registered = {m.split(":")[0] for m in pytest_opts["markers"]}
    assert registered == {"live_claude", "testsite", "real_data"}
    python_version = (ROOT / ".python-version").read_text(encoding="utf-8")
    assert python_version.strip().startswith("3.12")


# What `mypy --strict` enables (mypy 2.4 --help), less the global-only
# warn_redundant_casts.
STRICT_FLAGS = {
    "disallow_any_generics": True,
    "disallow_subclassing_any": True,
    "disallow_untyped_calls": True,
    "disallow_untyped_defs": True,
    "disallow_incomplete_defs": True,
    "check_untyped_defs": True,
    "disallow_untyped_decorators": True,
    "warn_unused_ignores": True,
    "warn_return_any": True,
    "implicit_reexport": False,
    "strict_equality": True,
    "extra_checks": True,
}


def test_mypy_config():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    mypy = pyproject["tool"]["mypy"]
    assert mypy["python_version"] == "3.12"
    assert mypy["plugins"] == ["pydantic.mypy"]
    assert mypy["files"] == ["src", "scripts"]
    # Libraries without stubs are listed one by one, never ignored globally.
    assert "ignore_missing_imports" not in mypy
    # `strict` in an override turns strict on for every module (mypy 2.4),
    # so the override spells out the per-module flags --strict enables.
    assert "strict" not in mypy
    assert mypy["warn_redundant_casts"] is True  # global only
    assert all("strict" not in o for o in mypy["overrides"])
    strict = [o for o in mypy["overrides"] if o.get("disallow_untyped_defs")]
    assert len(strict) == 1 and strict[0]["module"]
    assert {k: v for k, v in strict[0].items() if k != "module"} == STRICT_FLAGS


def test_ruff_config():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = pyproject["tool"]["ruff"]["lint"]
    assert {"BLE", "RUF100"} <= set(lint["select"])
    # A module not built yet is still sorted as ours (friction log, 20 Nov 2026).
    assert lint["isort"]["known-first-party"] == ["po_agent"]
    # Joey's hooks fail closed on any error by design.
    assert lint["per-file-ignores"][".claude/hooks/*"] == ["BLE"]


def ruff_codes(code: str, path: str) -> set[str]:
    """The codes `ruff check` reports on `code` as if it were the file at
    `path`, with the repo's config and no cache."""
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache"]
        + ["--output-format", "concise", "--stdin-filename", path, "-"],
        cwd=ROOT,
        input=code,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    # 0 = clean, 1 = findings; 2 = ruff itself failed (e.g. a broken config),
    # which would otherwise read as "no findings".
    assert result.returncode in (0, 1), result.stderr
    return {line.split()[1] for line in result.stdout.splitlines() if ": " in line}


BLIND_EXCEPT = "def f():\n    try:\n        pass\n    except Exception:\n        pass\n"


def test_lint_catches_a_blind_except():
    assert ruff_codes(BLIND_EXCEPT, "src/po_agent/probe.py") == {"BLE001"}


def test_lint_lets_the_hooks_catch_everything():
    assert ruff_codes(BLIND_EXCEPT, ".claude/hooks/probe.py") == set()


def test_lint_catches_an_unused_noqa():
    assert ruff_codes("X = 1  # noqa: E501\n", "src/po_agent/probe.py") == {"RUF100"}


@pytest.mark.parametrize("bad", ["private/notes.txt", "stray.pdf"])
def test_repo_data_only_rejects_a_staged_path(
    tmp_path, monkeypatch, capsys, check_script, bad
):
    # The pre-commit hook runs `scripts/check.py --repo-data-only`.
    repo = make_repo(tmp_path, [*CLEAN, bad])
    monkeypatch.setattr(check_script, "ROOT", repo)

    with pytest.raises(SystemExit) as exit_info:
        check_script.main(["--repo-data-only"])

    out = capsys.readouterr().out
    assert exit_info.value.code != 0
    assert f"repo-data: {bad}: " in out
    assert "check: failed at repo data" in out


def test_repo_data_only_runs_no_other_step(tmp_path, monkeypatch, capsys, check_script):
    repo = make_repo(tmp_path, CLEAN)
    monkeypatch.setattr(check_script, "ROOT", repo)
    monkeypatch.setattr(
        check_script,
        "STEPS",
        [("other", lambda: pytest.fail("--repo-data-only ran another step"))],
    )

    with pytest.raises(SystemExit) as exit_info:
        check_script.main(["--repo-data-only"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.splitlines() == [
        "check: repo data",
        "check: all passed",
    ]


def test_unknown_argument_is_refused(check_script):
    with pytest.raises(SystemExit) as exit_info:
        check_script.main(["--everything"])
    assert exit_info.value.code != 0


def test_plain_pytest_stays_serial():
    # Only check.py adds -n: a plain `uv run pytest` (seam 2 included) runs
    # one test at a time.
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = pyproject["tool"]["pytest"]["ini_options"]["addopts"].split()
    assert not any(
        opt.startswith(("-n", "--numprocesses", "--dist")) for opt in addopts
    )
    assert any(
        dep.startswith("pytest-xdist") for dep in pyproject["dependency-groups"]["dev"]
    )


def fake_quick_run(monkeypatch, check_script, collected: int) -> list[list[str]]:
    """Records every subprocess; a --collect-only run lists `collected` tests."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        stdout = ""
        if "--collect-only" in args:
            lines = [f"tests/test_x.py::test_{n}" for n in range(collected)]
            lines += ["", f"{collected} tests collected in 0.10s", ""]
            stdout = "\n".join(lines)
        return subprocess.CompletedProcess(args, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(check_script.subprocess, "run", fake_run)
    monkeypatch.setattr(check_script, "repo_data_violations", lambda root: [])
    return calls


def test_quick_runs_the_fast_checks_then_only_the_given_tests(
    monkeypatch, capsys, check_script
):
    calls = fake_quick_run(monkeypatch, check_script, collected=3)

    with pytest.raises(SystemExit) as exit_info:
        check_script.main(["--quick", "tests/test_check.py", "tests/test_guard.py"])

    python_m = [sys.executable, "-m"]
    paths = ["tests/test_check.py", "tests/test_guard.py"]
    assert exit_info.value.code == 0
    assert calls[:4] == [
        [*python_m, "ruff", "format", "--check", "--no-cache", "."],
        [*python_m, "ruff", "check", "--no-cache", "."],
        [*python_m, "mypy"],
        [sys.executable, "scripts/guard_check.py"],
    ]
    assert calls[-1] == [*python_m, "pytest", *paths, "-m", PYTEST_MARKERS]
    out = capsys.readouterr().out.splitlines()
    assert "check: repo data" in out
    assert out[-1] == "check: all passed"


def test_quick_runs_in_parallel_past_50_tests(monkeypatch, check_script):
    calls = fake_quick_run(monkeypatch, check_script, collected=51)

    with pytest.raises(SystemExit) as exit_info:
        check_script.main(["--quick", "tests"])

    assert exit_info.value.code == 0
    assert calls[-1] == [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-m",
        PYTEST_MARKERS,
        *PARALLEL,
    ]


def test_quick_stays_serial_at_50_tests(monkeypatch, check_script):
    calls = fake_quick_run(monkeypatch, check_script, collected=50)

    with pytest.raises(SystemExit):
        check_script.main(["--quick", "tests"])

    assert "-n" not in calls[-1]


def test_quick_needs_a_test_path(check_script):
    with pytest.raises(SystemExit) as exit_info:
        check_script.main(["--quick"])
    assert exit_info.value.code != 0


def test_quick_and_repo_data_only_are_exclusive(check_script):
    with pytest.raises(SystemExit) as exit_info:
        check_script.main(["--quick", "tests", "--repo-data-only"])
    assert exit_info.value.code != 0


# --- conflict markers (friction log, 25 Nov 2026; decisions, 25 Nov 2026,
# Checkpoint S-A friction decisions) ---

LT, EQ, GT = "<" * 7, "=" * 7, ">" * 7  # never at the start of a line here


def repo_with(root: Path, files: dict[str, bytes]) -> Path:
    """A temp git repo with `files` (path -> bytes) staged."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    subprocess.run(["git", "-C", str(root), "add", "--", *files], check=True)
    return root


CONFLICT = f"a\n{LT} HEAD\nours\n{EQ}\ntheirs\n{GT} origin/main\nb\n".encode()


def test_conflict_markers_are_named_by_line(tmp_path, check_script):
    repo = repo_with(tmp_path, {"docs/decisions.md": CONFLICT, "src/x.py": b"x = 1\n"})
    assert check_script.conflict_markers(repo) == [
        "docs/decisions.md:2: conflict marker",
        "docs/decisions.md:4: conflict marker",
        "docs/decisions.md:6: conflict marker",
    ]


@pytest.mark.parametrize(
    "text",
    [
        f"{LT}\n",  # a bare start marker
        f"{GT}\n",
        f"x\r\n{LT} HEAD\r\n",  # CRLF
    ],
)
def test_each_start_or_end_marker_is_found(tmp_path, check_script, text):
    repo = repo_with(tmp_path, {"a.txt": text.encode()})
    assert len(check_script.conflict_markers(repo)) == 1


@pytest.mark.parametrize(
    "text",
    [
        f"Title\n{EQ}\n",  # a Markdown heading underline, outside a conflict
        f"x = '{LT} HEAD'\n    {GT} indented\n",  # not at the line start
        f"{LT}{LT}\n",  # 14 in a row is not git's marker
        "plain text\n",
    ],
)
def test_text_that_only_looks_like_a_marker_passes(tmp_path, check_script, text):
    repo = repo_with(tmp_path, {"a.md": text.encode()})
    assert check_script.conflict_markers(repo) == []


def test_binary_and_untracked_files_are_skipped(tmp_path, check_script):
    repo = repo_with(tmp_path, {"a.bin": b"\0" + CONFLICT})
    (repo / "untracked.md").write_bytes(CONFLICT)
    assert check_script.conflict_markers(repo) == []


def test_conflict_markers_outside_a_git_repo_fail(tmp_path, check_script):
    assert check_script.conflict_markers(tmp_path) != []


def test_conflict_marker_step_fails_and_names_the_line(
    tmp_path, monkeypatch, capsys, check_script
):
    repo = repo_with(tmp_path, {"a.md": CONFLICT})
    monkeypatch.setattr(check_script, "ROOT", repo)
    step = dict(check_script.STEPS)["conflict markers"]

    assert step() is False
    assert "conflict-markers: a.md:2: conflict marker" in capsys.readouterr().out


def test_conflict_marker_step_passes_on_a_clean_repo(
    tmp_path, monkeypatch, capsys, check_script
):
    repo = repo_with(tmp_path, {"a.md": b"x\n"})
    monkeypatch.setattr(check_script, "ROOT", repo)
    step = dict(check_script.STEPS)["conflict markers"]

    assert step() is True
    assert "conflict-markers:" not in capsys.readouterr().out


# --- rerun after timeout (friction log, 24 Nov 2026; decisions, 25 Nov 2026,
# Checkpoint S-A friction decisions): only failed tests whose failure is a
# Playwright timeout are rerun, once, serially; anything else still fails. ---

PW_TIMEOUT = "playwright._impl._errors.TimeoutError: Locator.click: Timeout 2000ms"


def case(file: str, classname: str, name: str, problem: str = "", text: str = ""):
    """One xunit1 <testcase>, as pytest writes it on Windows (backslashes)."""
    body = f'<{problem} message="{text[:40]}">{text}</{problem}>' if problem else ""
    return (
        f'<testcase classname="{classname}" name="{name}" '
        f'file="{file}" line="1" time="0.1">{body}</testcase>'
    )


def junit(*cases: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">'
        + "".join(cases)
        + "</testsuite></testsuites>"
    )


TIMEOUT_A = case(
    "tests\\test_a.py", "tests.test_a", "test_one", "failure", f"E   {PW_TIMEOUT}"
)
TIMEOUT_B = case(
    "tests\\sub\\test_b.py",
    "tests.sub.test_b.TestB",
    "test_two[p.1-x y]",
    "error",
    f"failed on setup with {PW_TIMEOUT}",
)
ASSERTION = case(
    "tests\\test_c.py", "tests.test_c", "test_three", "failure", "assert 1 == 2"
)
PASSED = case("tests\\test_c.py", "tests.test_c", "test_four")
NODE_A = "tests/test_a.py::test_one"
NODE_B = "tests/sub/test_b.py::TestB::test_two[p.1-x y]"


def fake_pytest(monkeypatch, check_script, runs: list[tuple[int, str | None]]):
    """Each pytest call takes the next (exit code, junit report or None) and
    writes the report where --junitxml says; returns the calls made."""
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        code, report = runs[len(calls)]
        calls.append(args)
        if report is not None and "--junitxml" in args:
            target = Path(args[args.index("--junitxml") + 1])
            target.write_text(report, encoding="utf-8")
        return subprocess.CompletedProcess(args, code)

    monkeypatch.setattr(check_script.subprocess, "run", fake_run)
    return calls


def offline_tests_step(check_script):
    return check_script.STEPS[-1][1]


def test_a_green_run_is_not_rerun(monkeypatch, check_script):
    calls = fake_pytest(monkeypatch, check_script, [(0, junit(PASSED))])
    assert offline_tests_step(check_script)() is True
    assert len(calls) == 1


def test_timeouts_rerun_once_serially_and_pass(monkeypatch, capsys, check_script):
    calls = fake_pytest(
        monkeypatch,
        check_script,
        [(1, junit(TIMEOUT_A, PASSED, TIMEOUT_B)), (0, None)],
    )

    assert offline_tests_step(check_script)() is True

    assert len(calls) == 2
    assert calls[1] == [
        sys.executable,
        "-m",
        "pytest",
        NODE_A,
        NODE_B,
        "-m",
        PYTEST_MARKERS,
    ]
    out = capsys.readouterr().out
    assert "rerun after timeout" in out
    assert NODE_A in out and NODE_B in out


def test_a_timeout_that_fails_again_fails_the_check(monkeypatch, capsys, check_script):
    calls = fake_pytest(monkeypatch, check_script, [(1, junit(TIMEOUT_A)), (1, None)])

    assert offline_tests_step(check_script)() is False
    assert len(calls) == 2
    assert "rerun after timeout" in capsys.readouterr().out


def test_any_other_failure_is_never_rerun(monkeypatch, check_script):
    calls = fake_pytest(
        monkeypatch, check_script, [(1, junit(TIMEOUT_A, ASSERTION)), (0, None)]
    )

    assert offline_tests_step(check_script)() is False
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("code", "report"),
    [
        (2, junit(TIMEOUT_A)),  # interrupted
        (3, junit(TIMEOUT_A)),  # pytest internal error
        (4, None),  # usage error, no report
        (5, junit()),  # no tests collected
        (1, None),  # no report written
        (1, "not xml"),
        (1, junit(PASSED)),  # failed, but the report names no failure
    ],
)
def test_a_failed_run_without_timeouts_to_rerun_fails(
    monkeypatch, check_script, code, report
):
    calls = fake_pytest(monkeypatch, check_script, [(code, report), (0, None)])

    assert offline_tests_step(check_script)() is False
    assert len(calls) == 1


def test_a_case_whose_node_id_cant_be_rebuilt_is_not_rerun(monkeypatch, check_script):
    odd = case(
        "tests\\test_a.py", "elsewhere.test_a", "test_one", "failure", PW_TIMEOUT
    )
    calls = fake_pytest(monkeypatch, check_script, [(1, junit(odd)), (0, None)])

    assert offline_tests_step(check_script)() is False
    assert len(calls) == 1


PROBE = """\
import pytest
from playwright._impl._errors import TimeoutError


class TestA:
    @pytest.mark.parametrize("v", ["p.1", "x y"])
    def test_b(self, v):
        raise TimeoutError("Locator.click: Timeout 2000ms exceeded.")


def test_plain():
    assert 1 == 2
"""


def test_failed_tests_reads_a_real_parallel_pytest_report(tmp_path, check_script):
    # The node ids come from pytest's own report format, so pin it on a real run.
    (tmp_path / "tests" / "sub").mkdir(parents=True)
    (tmp_path / "tests" / "sub" / "test_probe.py").write_text(PROBE, encoding="utf-8")
    report = tmp_path / "junit.xml"
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-p", "no:cacheprovider"]
        + ["-n", "2", "--junitxml", str(report), "-o", "junit_family=xunit1"],
        cwd=tmp_path,
        capture_output=True,
    )

    assert sorted(check_script.failed_tests(report)) == [
        ("tests/sub/test_probe.py::TestA::test_b[p.1]", True),
        ("tests/sub/test_probe.py::TestA::test_b[x y]", True),
        ("tests/sub/test_probe.py::test_plain", False),
    ]

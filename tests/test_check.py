"""Tests for scripts/check.py: the repo-data rule and the check command's steps."""

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PYTEST_MARKERS = "not live_claude and not testsite and not real_data"


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
        "config/live.toml",
        "config/Live-prod.TOML",
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
        "ruff format --check .",
        "ruff check .",
        "guard check",
        "repo data",
        f'pytest tests -m "{PYTEST_MARKERS}"',
    ]


def test_steps_run_the_spec_commands(monkeypatch, check_script):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs.get("cwd")))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(check_script.subprocess, "run", fake_run)
    command_steps = [run for name, run in check_script.STEPS if name != "repo data"]
    for run in command_steps:
        assert run() is True

    python_m = [sys.executable, "-m"]
    assert calls == [
        ([*python_m, "ruff", "format", "--check", "."], check_script.ROOT),
        ([*python_m, "ruff", "check", "."], check_script.ROOT),
        ([sys.executable, "scripts/guard_check.py"], check_script.ROOT),
        ([*python_m, "pytest", "tests", "-m", PYTEST_MARKERS], check_script.ROOT),
    ]


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

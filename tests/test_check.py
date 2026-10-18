"""Tests for scripts/check.py: the repo-data rule and the check command's steps."""

import importlib.util
import subprocess
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
    "tests/seam1/fixtures/pdfs/a.pdf",
    "tests/seam1/fixtures/pdfs/sub/B.PDF",
]


def test_clean_repo_has_no_violations(tmp_path, check_script):
    repo = make_repo(tmp_path, CLEAN)
    assert check_script.repo_data_violations(repo) == []


@pytest.mark.parametrize(
    "bad",
    [
        "private/notes.txt",
        "logs/run.jsonl",
        "state/s.json",
        ".playwright-cli/snap.yml",
        ".state/s.json",
        "traces/run.json",
        "src/state/x.py",
        "src/.state/x.py",
        "src/traces/x.py",
        "po.pdf",
        "docs/PO.Pdf",
        "tests/seam1/fixtures/a.pdf",
        "trace.zip",
        "out/run.trace.zip",
        "net.har",
        "rec.webm",
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
        "repo data",
        f'pytest tests -m "{PYTEST_MARKERS}"',
    ]


def test_project_config():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["scripts"]["po-agent"] == "po_agent.cli:main"
    pytest_opts = pyproject["tool"]["pytest"]["ini_options"]
    assert "--strict-markers" in pytest_opts["addopts"]
    registered = {m.split(":")[0] for m in pytest_opts["markers"]}
    assert registered == {"live_claude", "testsite", "real_data"}
    python_version = (ROOT / ".python-version").read_text(encoding="utf-8")
    assert python_version.strip().startswith("3.12")

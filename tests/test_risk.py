"""Tests for scripts/risk.py, which computes a PR's risk level from the files it
changes (docs/workflow.md, Production build loop step 5). Offline: the
classification takes path lists and numstat text; main() gets a fake git."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def risk():
    # scripts/ isn't a package, so load the file directly.
    spec = importlib.util.spec_from_file_location("risk", ROOT / "scripts" / "risk.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "path",
    (
        "src/po_agent/mysys/guard.py",
        "src/po_agent/mysys/driver.py",
        "src/po_agent/mysys/booking.py",
        "src/po_agent/mysys/new_screen.py",
        "src/po_agent/b1/booker.py",
        "src/po_agent/b1/reader_rules.py",
        "src/po_agent/b1/readers.py",
        "src/po_agent/b1/decision.py",
        "src/po_agent/b1/address.py",
        "src/po_agent/summit/readers.py",  # SPEC Client 2: readers, rules, decision engine
        "src/po_agent/summit/decision.py",
        "src/po_agent/summit/companies.py",
        "scripts/guard_check.py",
        "scripts/check.py",
        "scripts/risk.py",
        "scripts/verify_pr.py",
        ".claude/hooks/guard_bash.py",
        ".claude/hooks/protect_paths.py",
        ".claude/settings.json",
        ".claude/settings.local.json",
        ".github/workflows/ci.yml",
        ".github/workflows/heartbeat.yml",
    ),
)
def test_high_paths(risk, path):
    assert risk.classify(path) == "high"


@pytest.mark.parametrize(
    "path",
    (
        "src/po_agent/core/run.py",
        "src/po_agent/core/output.py",
        "src/po_agent/b1/models.py",
        "src/po_agent/cli.py",
        "src/po_agent/mysysx.py",  # not inside mysys/
        "src/po_agent/summitx.py",  # not inside summit/
        "scripts/heartbeat_check.py",
        "scripts/macmini-run.sh",
        "scripts/risk_helper.py",  # near misses: whole paths only
        "scripts/old/verify_pr.py",
    ),
)
def test_medium_paths(risk, path):
    assert risk.classify(path) == "medium"


@pytest.mark.parametrize(
    "path",
    (
        "docs/workflow.md",
        "docs/decisions.md",
        "SPEC.md",
        "CLAUDE.md",
        "tests/test_guard.py",
        "tests/seam2/test_booking.py",
        ".claude/skills/start-task/SKILL.md",
        "tasks/todo.md",
        "README.md",
    ),
)
def test_low_paths(risk, path):
    assert risk.classify(path) == "low"


@pytest.mark.parametrize(
    ("paths", "level"),
    (
        ([], "low"),
        (["docs/a.md", "tests/test_x.py"], "low"),
        (["docs/a.md", "scripts/heartbeat_check.py", "tests/test_risk.py"], "medium"),
        (
            ["docs/a.md", "src/po_agent/core/run.py", "src/po_agent/mysys/guard.py"],
            "high",
        ),
        (["src/po_agent/b1/address.py", "docs/a.md"], "high"),
    ),
)
def test_highest_file_wins(risk, paths, level):
    assert risk.assess(paths) == level


def test_parse_numstat_counts_lines_and_binary(risk):
    text = "10\t2\tscripts/risk.py\n120\t0\ttests/test_risk.py\n-\t-\tdocs/img.png\n"
    paths, lines = risk.parse_numstat(text)
    assert paths == ["scripts/risk.py", "tests/test_risk.py", "docs/img.png"]
    assert lines == 132


def test_parse_numstat_empty(risk):
    assert risk.parse_numstat("") == ([], 0)


def fake_git(numstat: str):
    calls = []

    def run(args):
        calls.append(args)
        return numstat

    return run, calls


def test_main_prints_level_and_reason(risk, capsys):
    run, calls = fake_git("5\t1\tdocs/a.md\n3\t3\tsrc/po_agent/mysys/guard.py\n")
    assert risk.main(run_git=run) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "risk: high"
    assert any("src/po_agent/mysys/guard.py" in line for line in out[1:])
    assert not any(line.startswith("warning:") for line in out)
    # The diff is the PR's: against the merge base with origin/main.
    assert any("origin/main...HEAD" in args for args in calls)


def test_main_warns_over_400_lines(risk, capsys):
    run, _ = fake_git("300\t101\tdocs/a.md\n")
    assert risk.main(run_git=run) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "risk: low"
    assert any(line.startswith("warning:") and "401" in line for line in out)


def test_main_no_warning_at_400_lines(risk, capsys):
    run, _ = fake_git("300\t100\tdocs/a.md\n")
    risk.main(run_git=run)
    assert not any(
        line.startswith("warning:") for line in capsys.readouterr().out.splitlines()
    )


def test_main_empty_diff_is_low(risk, capsys):
    run, _ = fake_git("")
    assert risk.main(run_git=run) == 0
    assert capsys.readouterr().out.splitlines()[0] == "risk: low"


def test_main_takes_a_head_ref(risk, capsys):
    # /verify-pr runs it from the advisor's checkout on the PR's branch.
    run, calls = fake_git("1\t0\tdocs/a.md\n")
    assert risk.main(["origin/feat/x"], run_git=run) == 0
    assert any("origin/main...origin/feat/x" in args for args in calls)

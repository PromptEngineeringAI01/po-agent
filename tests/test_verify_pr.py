"""Tests for scripts/verify_pr.py, the mechanical half of /verify-pr (audit
fix #2, 24 Nov 2026). Each test builds a temp git repo with a fake
`origin/main` and fake branch commits, then runs the script on it as Joey's
advisor would: `verify_pr.py <ref> --body-file <file>`. One commit carries
every variant of a rule where it can, so each run pins several cases.

The live host and the Anthropic key's variable name are never written here
whole (CLAUDE.md Must never #3 and #5): the host comes from `LIVE_HOST`, the
name is built from parts. The em dash is `chr(0x2014)`, never the character.
"""

import os
import subprocess
import sys
from pathlib import Path

from po_agent.core.config import LIVE_HOST

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "verify_pr.py"
KEY_NAME = "ANTHROPIC" + "_API_KEY"
EM_DASH = chr(0x2014)
ACTIONS = ("click", "fill", "check", "set_input_files", "evaluate", "dispatch_event")


def body(risk: str = "Medium") -> str:
    return (
        "## Intent\n\nTurn the mechanical checks into a script.\n\n"
        "## What changed\n\nscripts/verify_pr.py and its tests.\n\n"
        f"## Risk\n\n**{risk}** (`uv run scripts/risk.py`). Safe: it only reads.\n\n"
        "## Testing\n\ncheck: all passed\n"
    )


def git_env() -> dict[str, str]:
    # Inside a git hook, git sets GIT_DIR and friends for the outer repo; the
    # user's own config (signing, hooks, autocrlf) must not reach the temp repo.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@t",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
    )
    return env


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=git_env(),
    ).stdout.strip()


def commit(repo: Path, subject: str, files: dict[str, str]) -> str:
    """Write `files`, commit them all; the new commit's 7-character sha."""
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", subject)
    return git(repo, "rev-parse", "HEAD")[:7]


def make_repo(tmp_path: Path, base: dict[str, str] | None = None) -> Path:
    """A repo whose `origin/main` is one commit, with branch `feature` checked out."""
    repo = tmp_path / "repo"
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(repo)], check=True, env=git_env()
    )
    commit(repo, "docs: base", {"README.md": "base\n", **(base or {})})
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "switch", "-q", "-c", "feature")
    return repo


def run(
    repo: Path, pr_body: str | None = None, ref: str = "feature"
) -> tuple[int, list[str]]:
    args = [sys.executable, str(SCRIPT), ref]
    if pr_body is not None:
        body_file = repo.parent / "body.md"
        body_file.write_text(pr_body, encoding="utf-8")
        args += ["--body-file", str(body_file)]
    result = subprocess.run(
        args,
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=git_env(),
    )
    return result.returncode, result.stdout.splitlines()


def fails(lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith("FAIL:")]


# --- a clean PR ---------------------------------------------------------------


def test_clean_branch_passes(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "test: pin x", {"tests/test_x.py": "def test_x():\n    pass\n"})
    commit(repo, "feat: x", {"src/po_agent/x.py": "X = 1\n"})
    commit(repo, "refactor: tidy x", {"src/po_agent/x.py": "X = 2\n"})
    commit(repo, "docs: note x", {"docs/x.md": "x - done\n"})
    assert run(repo, body("Medium")) == (0, ["verify_pr: 0 fail, 0 warn"])


# --- rule 1: tests only in test: commits, no src/ in a test: commit ------------


def test_tests_outside_a_test_commit_fail_on_the_given_ref(tmp_path):
    repo = make_repo(tmp_path)
    sha = commit(repo, "feat: x", {"src/po_agent/x.py": "X = 1\n", "tests/a.py": ""})
    git(repo, "switch", "-q", "main")  # the ref, not HEAD, is what's checked
    code, lines = run(repo, body("Medium"))
    assert code == 1
    assert fails(lines) == [
        f"FAIL: tests/ changed outside a test: commit: {sha} tests/a.py"
    ]
    assert lines[-1] == "verify_pr: 1 fail, 0 warn"


def test_src_in_a_test_commit_fails(tmp_path):
    repo = make_repo(tmp_path)
    sha = commit(
        repo, "test: x", {"tests/test_x.py": "", "src/po_agent/x.py": "X = 1\n"}
    )
    code, lines = run(repo, body("Medium"))
    assert code == 1
    assert fails(lines) == [
        f"FAIL: src/ changed in a test: commit: {sha} src/po_agent/x.py"
    ]


# --- rule 2: Conventional Commit subjects -------------------------------------


def test_non_conventional_subjects_fail_in_commit_order(tmp_path):
    repo = make_repo(tmp_path)
    subjects = ("Update the docs", "feature: x", "feat x", "feat(docs): x", "test:x")
    shas = [
        commit(repo, subject, {f"docs/{n}.md": "x\n"})
        for n, subject in enumerate(subjects)
    ]
    code, lines = run(repo, body("Low"))
    assert code == 1
    kinds = "FAIL: not a Conventional Commit (feat, fix, test, docs, chore, refactor):"
    assert fails(lines) == [
        f"{kinds} {shas[0]} Update the docs",
        f"{kinds} {shas[1]} feature: x",
        f"{kinds} {shas[2]} feat x",
        f"{kinds} {shas[3]} feat(docs): x",
        f"{kinds} {shas[4]} test:x",
    ]


def test_merge_commits_are_skipped(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "docs: a", {"docs/a.md": "a\n"})
    git(repo, "switch", "-q", "-c", "side", "main")
    commit(repo, "docs: b", {"docs/b.md": "b\n"})
    git(repo, "switch", "-q", "feature")
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "side")
    assert git(repo, "log", "-1", "--format=%s").startswith("Merge branch")
    assert run(repo, body("Low")) == (0, ["verify_pr: 0 fail, 0 warn"])


# --- rule 3: no em dash in added lines ----------------------------------------


def test_em_dash_fails_only_in_added_lines(tmp_path):
    repo = make_repo(tmp_path, {"docs/a.md": f"old {EM_DASH} line\n"})
    commit(
        repo, "docs: more", {"docs/a.md": f"old {EM_DASH} line\nnew {EM_DASH} line\n"}
    )
    code, lines = run(repo, body("Low"))
    assert code == 1
    assert fails(lines) == ["FAIL: em dash in an added line: docs/a.md:2"]


# --- rule 4: guarded actions, live host, the Anthropic key name ---------------


def test_playwright_actions_outside_guard_fail(tmp_path):
    repo = make_repo(tmp_path)
    calls = "".join(f"page.{action}(target)\n" for action in ACTIONS)
    commit(repo, "feat: x", {"src/po_agent/x.py": calls})
    code, lines = run(repo, body("Medium"))
    assert code == 1
    where = "FAIL: Playwright action outside src/po_agent/mysys/guard.py:"
    assert fails(lines) == [
        f"{where} src/po_agent/x.py:1",
        f"{where} src/po_agent/x.py:2",
        f"{where} src/po_agent/x.py:3",
        f"{where} src/po_agent/x.py:4",
        f"{where} src/po_agent/x.py:5",
        f"{where} src/po_agent/x.py:6",
    ]


def test_playwright_actions_in_guard_and_longer_names_pass(tmp_path):
    repo = make_repo(tmp_path)
    guard_lines = "".join(f"locator.{action}(value)\n" for action in ACTIONS)
    commit(
        repo,
        "feat: x",
        {
            "src/po_agent/mysys/guard.py": guard_lines,
            "scripts/x.py": "guard_check(paths)\nrun_checks(steps)\nbox.checked()\n",
        },
    )
    code, lines = run(repo, body("High"))
    assert (code, fails(lines)) == (0, [])


def test_playwright_action_names_in_non_python_files_pass(tmp_path):
    # Prose can't call anything; guard_check.py's AST scan of .py files is the
    # control (decisions, 24 Nov 2026). The verify-pr skill lists these names.
    repo = make_repo(tmp_path)
    prose = "".join(f"Never call {action}( outside the guard.\n" for action in ACTIONS)
    commit(
        repo,
        "docs: x",
        {
            "docs/x.md": prose,
            ".claude/skills/x/SKILL.md": prose,
            "notes/x.txt": "page.click(target)\n",
        },
    )
    code, lines = run(repo, body("High"))
    assert (code, fails(lines)) == (0, [])


def test_playwright_action_in_any_py_file_outside_guard_fails(tmp_path):
    # By extension, not folder: a .py under docs/ still fails.
    repo = make_repo(tmp_path)
    commit(
        repo,
        "docs: x",
        {"docs/example.py": "page.fill(target)\n", "docs/example.md": "fill(\n"},
    )
    code, lines = run(repo, body("Medium"))
    assert code == 1
    assert fails(lines) == [
        "FAIL: Playwright action outside src/po_agent/mysys/guard.py: docs/example.py:1"
    ]


def test_live_host_and_key_name_still_fail_in_markdown(tmp_path):
    repo = make_repo(tmp_path)
    commit(
        repo,
        "docs: x",
        {
            "docs/x.md": (
                f"Open https://{LIVE_HOST}/ and click( it.\nSet {KEY_NAME} first.\n"
            )
        },
    )
    code, lines = run(repo, body("Medium"))
    assert code == 1
    assert fails(lines) == [
        "FAIL: live host outside its allowed files: docs/x.md:1",
        "FAIL: Anthropic key variable outside tests/test_config_secrets.py:"
        " docs/x.md:2",
    ]


def test_live_host_outside_its_files_fails_in_any_case(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "test: x", {"tests/test_hooks_extra.py": f"H = '{LIVE_HOST}'\n"})
    commit(
        repo,
        "feat: x",
        {
            "src/po_agent/x.py": f'URL = "https://{LIVE_HOST}/index.php"\n',
            "docs/x.md": f"Open https://{LIVE_HOST.upper()}/ by hand.\n",
        },
    )
    code, lines = run(repo, body("Medium"))
    assert code == 1
    assert fails(lines) == [
        "FAIL: live host outside its allowed files: docs/x.md:1",
        "FAIL: live host outside its allowed files: src/po_agent/x.py:1",
        "FAIL: live host outside its allowed files: tests/test_hooks_extra.py:1",
    ]


def test_live_host_in_its_files_and_the_test_host_pass(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "test: x", {"tests/test_hooks.py": f'HOST = "{LIVE_HOST}"\n'})
    commit(
        repo,
        "feat: x",
        {
            "src/po_agent/core/config.py": f'LIVE_HOST = "{LIVE_HOST}"\n',
            "config/live.toml": f'base_url = "https://{LIVE_HOST}/"\n',
            ".claude/hooks/guard_bash.py": f"# {LIVE_HOST}\n",
            "src/po_agent/x.py": f'URL = "https://test-{LIVE_HOST}/"\n',
        },
    )
    code, lines = run(repo, body("High"))
    assert (code, fails(lines)) == (0, [])


def test_anthropic_key_name_outside_its_test_fails(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "feat: x", {"src/po_agent/x.py": f'os.environ["{KEY_NAME}"]\n'})
    code, lines = run(repo, body("Medium"))
    assert code == 1
    assert fails(lines) == [
        "FAIL: Anthropic key variable outside tests/test_config_secrets.py:"
        " src/po_agent/x.py:1"
    ]


def test_anthropic_key_name_in_its_test_passes(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "test: x", {"tests/test_config_secrets.py": f'NAME = "{KEY_NAME}"\n'})
    assert run(repo, body("Low")) == (0, ["verify_pr: 0 fail, 0 warn"])


def test_this_script_and_its_tests_never_write_them_whole():
    for path in (SCRIPT, Path(__file__)):
        text = path.read_text(encoding="utf-8")
        assert LIVE_HOST not in text.lower()
        assert KEY_NAME not in text
        assert EM_DASH not in text


# --- rule 5: dependency files -------------------------------------------------


def test_dependency_file_changes_warn(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "chore: deps", {"uv.lock": "x = 1\n", "pyproject.toml": "x = 1\n"})
    assert run(repo, body("Low")) == (
        0,
        [
            "WARN: dependency file changed (the PR must say Joey approved it):"
            " pyproject.toml",
            "WARN: dependency file changed (the PR must say Joey approved it): uv.lock",
            "verify_pr: 0 fail, 2 warn",
        ],
    )


# --- rule 6: the PR body ------------------------------------------------------


def test_body_without_sections_fails_each(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "docs: x", {"docs/x.md": "x\n"})
    code, lines = run(repo, "Intent, what changed, risk and testing: all fine.\n")
    assert code == 1
    assert fails(lines) == [
        "FAIL: PR body lacks the Intent section",
        "FAIL: PR body lacks the What changed section",
        "FAIL: PR body lacks the Risk section",
        "FAIL: PR body lacks the Testing section",
    ]


def test_stated_risk_below_computed_fails(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "feat: x", {"scripts/x.py": "X = 1\n"})
    code, lines = run(repo, body("Low"))
    assert code == 1
    assert fails(lines) == ["FAIL: stated risk low is below the computed medium"]


def test_stated_risk_above_computed_passes(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "docs: x", {"docs/x.md": "x\n"})
    assert run(repo, body("High")) == (0, ["verify_pr: 0 fail, 0 warn"])


def test_risk_section_without_a_level_fails(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "docs: x", {"docs/x.md": "x\n"})
    code, lines = run(repo, body("Unclear"))
    assert code == 1
    assert fails(lines) == [
        "FAIL: the Risk section states no level (low, medium or high)"
    ]


def test_no_body_given_warns(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "docs: x", {"docs/x.md": "x\n"})
    assert run(repo) == (
        0,
        [
            "WARN: PR body not checked (give --pr or --body-file)",
            "verify_pr: 0 fail, 1 warn",
        ],
    )


# --- rule 7: what the LLM must still look at ----------------------------------


def test_safety_sensitive_files_are_flagged_for_review(tmp_path):
    repo = make_repo(tmp_path)
    safety = (
        "src/po_agent/mysys/guard.py",
        "scripts/guard_check.py",
        ".claude/skills/x/SKILL.md",
        ".github/workflows/check.yml",
        "scripts/check.py",
        "config/test.toml",
        "docs/macmini-setup.md",
        "scripts/macmini-run.sh",
        "scripts/au.com.prompteng.po-agent.plist",
        "src/po_agent/b1/address.py",
        "scripts/risk.py",
        "scripts/verify_pr.py",
    )
    # Not flagged: a doc, and a near miss of a safety file's name.
    others = ("docs/x.md", "scripts/risk_helper.py")
    commit(repo, "chore: x", {path: "x = 1\n" for path in (*safety, *others)})
    review = "REVIEW: safety-sensitive file changed:"
    assert run(repo, body("High")) == (
        0,
        [
            f"{review} .claude/skills/x/SKILL.md",
            f"{review} .github/workflows/check.yml",
            f"{review} config/test.toml",
            f"{review} docs/macmini-setup.md",
            f"{review} scripts/au.com.prompteng.po-agent.plist",
            f"{review} scripts/check.py",
            f"{review} scripts/guard_check.py",
            f"{review} scripts/macmini-run.sh",
            f"{review} scripts/risk.py",
            f"{review} scripts/verify_pr.py",
            f"{review} src/po_agent/b1/address.py",
            f"{review} src/po_agent/mysys/guard.py",
            "verify_pr: 0 fail, 0 warn",
        ],
    )


def test_over_400_lines_is_flagged_for_review(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "docs: big", {"docs/big.md": "x\n" * 401})
    assert run(repo, body("Low")) == (
        0,
        [
            "REVIEW: 401 lines changed (over 400); consider splitting the PR",
            "verify_pr: 0 fail, 0 warn",
        ],
    )


def test_400_lines_is_not_flagged(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "docs: big", {"docs/big.md": "x\n" * 400})
    assert run(repo, body("Low")) == (0, ["verify_pr: 0 fail, 0 warn"])

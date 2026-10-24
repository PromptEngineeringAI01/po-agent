"""Tests for the commit-time and CI checks.

`.pre-commit-config.yaml` (gitleaks + the repo-data rule), `.gitleaks.toml`
(an `sk-ant-` rule; only the hook test's fake key allowed) and
`.github/workflows/check.yml`.
"""

import re
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
HOOK_TEST = "tests/test_hooks.py"


def load_yaml(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fake_key() -> str:
    # Read from the hook test itself, so the key isn't written out a second
    # time in a file gitleaks would flag.
    text = (ROOT / HOOK_TEST).read_text(encoding="utf-8")
    match = re.search(r'^FAKE_KEY = "([^"]+)"$', text, re.MULTILINE)
    assert match, f"FAKE_KEY not found in {HOOK_TEST}"
    return match.group(1)


@pytest.fixture(scope="module")
def gitleaks() -> dict:
    return tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def precommit_hooks() -> dict[str, tuple[dict, dict]]:
    """Hook id -> (repo entry, hook entry)."""
    hooks = {}
    for repo in load_yaml(".pre-commit-config.yaml")["repos"]:
        for hook in repo["hooks"]:
            hooks[hook["id"]] = (repo, hook)
    return hooks


@pytest.fixture(scope="module")
def ci_steps() -> list[dict]:
    return load_yaml(".github/workflows/check.yml")["jobs"]["check"]["steps"]


# --- pre-commit ---


def test_precommit_runs_gitleaks_on_staged_changes(precommit_hooks):
    repo, _ = precommit_hooks["gitleaks"]
    assert repo["repo"] == "https://github.com/gitleaks/gitleaks"
    assert re.fullmatch(r"v\d+\.\d+\.\d+", repo["rev"])


def test_precommit_runs_the_repo_data_rule(precommit_hooks):
    repo, hook = precommit_hooks["repo-data"]
    assert repo["repo"] == "local"
    assert hook["entry"].split()[-2:] == ["scripts/check.py", "--repo-data-only"]
    # The rule reads the whole index, not the changed files pre-commit passes.
    assert hook["pass_filenames"] is False
    assert hook["always_run"] is True


# --- gitleaks ---


def sk_ant_rule(gitleaks: dict) -> dict:
    (rule,) = [r for r in gitleaks["rules"] if "sk-ant-" in r.get("keywords", [])]
    return rule


def test_gitleaks_keeps_the_default_rules(gitleaks):
    assert gitleaks["extend"]["useDefault"] is True
    assert not gitleaks["extend"].get("disabledRules")


@pytest.mark.parametrize(
    "secret",
    [
        "sk-ant-api03-" + "A1b2_C3d4-" * 3,
        "sk-ant-admin01-" + "x" * 20,
        # The default rule needs a full-length key; this one is short.
        "sk-ant-" + "0" * 20,
    ],
)
def test_gitleaks_flags_any_sk_ant_key(gitleaks, fake_key, secret):
    regex = re.compile(sk_ant_rule(gitleaks)["regex"])
    assert regex.search(f'key = "{secret}"')
    assert regex.search(f'key = "{fake_key}"')


@pytest.mark.parametrize(
    "text",
    ["sk-ant-…", "sk-ant-[A-Za-z0-9_-]{20,}", "sk-ant-" + "x" * 19],
)
def test_gitleaks_ignores_docs_mentions(gitleaks, text):
    assert not re.search(sk_ant_rule(gitleaks)["regex"], text)


def allowlists(gitleaks: dict) -> list[dict]:
    lists = list(gitleaks.get("allowlists", []))
    if "allowlist" in gitleaks:
        lists.append(gitleaks["allowlist"])
    for rule in gitleaks.get("rules", []):
        lists.extend(rule.get("allowlists", []))
        if "allowlist" in rule:
            lists.append(rule["allowlist"])
    return lists


def test_gitleaks_allows_only_the_fake_key_in_the_hook_test(gitleaks, fake_key):
    (allow,) = allowlists(gitleaks)
    assert allow in sk_ant_rule(gitleaks).get("allowlists", [])
    # Both the path and the exact key must match (D4, stricter than path only).
    assert allow["condition"] == "AND"
    assert set(allow) <= {"description", "condition", "paths", "regexes"}

    def allowed(path: str, secret: str) -> bool:
        return any(re.search(p, path) for p in allow["paths"]) and any(
            re.search(r, secret) for r in allow["regexes"]
        )

    assert allowed(HOOK_TEST, fake_key)
    assert not allowed(HOOK_TEST, fake_key + "X")
    assert not allowed(HOOK_TEST, "sk-ant-api03-" + "R" * 30)
    for other in ["tests/test_hooks.py.bak", "x/tests/test_hooks.py", "README.md"]:
        assert not allowed(other, fake_key)


# --- CI ---


def test_ci_runs_on_push_and_pull_request():
    workflow = (ROOT / ".github/workflows/check.yml").read_text(encoding="utf-8")
    # PyYAML reads the bare key `on` as True.
    triggers = yaml.safe_load(workflow)[True]
    assert set(triggers) == {"push", "pull_request"}


def test_ci_steps_in_order(ci_steps):
    uses = [s["uses"].split("@")[0] for s in ci_steps if "uses" in s]
    runs = [s["run"] for s in ci_steps if "run" in s]
    assert uses == [
        "actions/checkout",
        "astral-sh/setup-uv",
        "gitleaks/gitleaks-action",
    ]
    assert runs == [
        "uv sync --locked",
        "uv run playwright install --with-deps chromium",
        "uv run scripts/check.py",
    ]
    assert ci_steps[-1]["uses"].startswith("gitleaks/gitleaks-action@")


def test_ci_actions_are_pinned_to_a_commit(ci_steps):
    for step in ci_steps:
        if "uses" in step:
            assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


def test_ci_checkout_has_full_history_for_gitleaks(ci_steps):
    checkout = ci_steps[0]["with"]
    assert checkout["fetch-depth"] == 0
    assert checkout["persist-credentials"] is False


def test_ci_uses_no_secret_but_the_github_token():
    workflow = (ROOT / ".github/workflows/check.yml").read_text(encoding="utf-8")
    assert set(re.findall(r"secrets\.(\w+)", workflow)) == {"GITHUB_TOKEN"}


def test_ci_token_is_read_only():
    permissions = load_yaml(".github/workflows/check.yml")["permissions"]
    assert set(permissions.values()) == {"read"}


def test_ci_gitleaks_matches_precommit(ci_steps, precommit_hooks):
    env = ci_steps[-1]["env"]
    repo, _ = precommit_hooks["gitleaks"]
    assert env["GITLEAKS_CONFIG"] == ".gitleaks.toml"
    assert "v" + env["GITLEAKS_VERSION"] == repo["rev"]
    # Don't publish findings: no SARIF artifact, no PR comment.
    assert env["GITLEAKS_ENABLE_UPLOAD_ARTIFACT"] is False
    assert env["GITLEAKS_ENABLE_COMMENTS"] is False

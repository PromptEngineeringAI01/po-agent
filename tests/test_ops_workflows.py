"""Static checks on the 7.1 ops workflows: `heartbeat.yml` (missed-heartbeat
check) and `alert-email.yml` (the bot comment that makes GitHub email Joey
about an alert issue opened with his own token)."""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def steps(workflow: dict) -> list[dict]:
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


@pytest.mark.parametrize(
    ("name", "permissions"),
    (
        ("heartbeat.yml", {"contents": "read", "issues": "write"}),
        ("alert-email.yml", {"issues": "write"}),
    ),
)
def test_least_permissions_and_no_expression_in_a_shell(name, permissions):
    workflow = load(name)

    assert workflow["permissions"] == permissions
    for step in steps(workflow):
        # An issue title or body expanded into `run:` could inject commands.
        assert "${{" not in step.get("run", "")
        if "uses" in step:
            ref = step["uses"].split("@", 1)[1]
            assert len(ref) == 40, f"{step['uses']} is not pinned by commit SHA"


def test_heartbeat_runs_every_30_minutes_in_the_perth_window():
    triggers = load("heartbeat.yml")[True]  # YAML reads the key `on` as True

    assert triggers["schedule"] == [{"cron": "7,37 1-11 * * 1-5"}]


def test_alert_email_comments_once_on_po_agent_alert_issues_only():
    workflow = load("alert-email.yml")
    text = (WORKFLOWS / "alert-email.yml").read_text(encoding="utf-8")

    assert workflow[True] == {"issues": {"types": ["opened", "labeled"]}}
    assert "pull_request_target" not in text
    # One run at a time per issue, so `opened` and `labeled` can't both comment.
    assert workflow["concurrency"]["group"] == (
        "alert-email-${{ github.event.issue.number }}"
    )
    assert workflow["concurrency"].get("cancel-in-progress", False) is False
    (job,) = workflow["jobs"].values()
    condition = " ".join(job["if"].split())
    assert "contains(github.event.issue.labels.*.name, 'po-agent-alert')" in condition
    assert "github.event.issue.user.type != 'Bot'" in condition
    (step,) = job["steps"]
    assert step["env"]["ISSUE"] == "${{ github.event.issue.number }}"
    assert "<!-- po-agent-alert-email -->" in step["run"]

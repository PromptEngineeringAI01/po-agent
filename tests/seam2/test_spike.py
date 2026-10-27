"""Seam 2, the spike on the MySys test site (task 1.8; marker testsite).

Read-only: log in, set and read back the Note Pool filters, read the list
once. Run after a reset (docs/workflow.md 6.1). Assertions use counts, the
trial internal numbers and action names only, never page text.
"""

import json

import pytest

from po_agent import cli
from po_agent.core import run
from po_agent.mysys import driver

pytestmark = pytest.mark.testsite

READ_ONLY_ACTIONS = {
    "login_username",
    "login_password",
    "login_submit",
    "open_project_tab",
    "open_note_pool",
    "set_pool_filter",
    "set_locked_filter",
    "refresh_note_pool",
}


def test_spike_reads_the_note_pool_and_finds_the_three_trial_notes(
    page, guard, config, credentials, check_note_pool_reset
):
    driver.go_home(page, str(config.base_url))
    driver.login(
        guard,
        page,
        credentials["mysys_test_username"],
        credentials["mysys_test_password"],
    )
    panel = driver.open_note_pool(guard, page)
    driver.set_note_pool_filters(guard, panel, config.pool_name)
    listing = driver.read_note_pool(guard, panel)

    check_note_pool_reset(listing)
    found = run.eligible_notes(listing.rows, config.title_rule, config.pool_name)
    assert sorted(note.internal_no for note in found) == sorted(
        ["2609017B", "2609034B", "2610002B"]
    )
    assert {action for action, _ in guard.history} <= READ_ONLY_ACTIONS
    assert all(outcome == "done" for _, outcome in guard.history)


def test_spike_command_prints_eligible_3(credentials, capsys):
    code = cli.main(["spike", "--site", "test"])

    lines = capsys.readouterr().out.splitlines()
    summary = json.loads(lines[-1].removeprefix("RUN_SUMMARY "))
    assert code == 0
    assert summary["mode"] == "spike"
    assert summary["eligible"] == 3
    assert summary["exit_code"] == 0

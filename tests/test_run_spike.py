"""Tests for core/run.py's spike and its CLI wiring (task 1.8).

The driver is replaced by a fake, so nothing opens a browser. The spike reads
the Note Pool once and prints counts only (SPEC.md -> Code style).
"""

import json
from contextlib import contextmanager

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.b1.models import NotePoolRow
from po_agent.core import run
from po_agent.core.errors import LoginFailed
from po_agent.mysys import driver

POOL = "Agent Pool"
ADDRESS = "Lot 123 (#45) Sample Lane Sampleville 6000 WA"


def row(note_id: str, cell: str, *, assignee=POOL, project="---") -> NotePoolRow:
    return NotePoolRow(
        note_id=note_id, subject_note=cell, project=project, assignee=assignee
    )


ROWS = (
    row("300001", f"Please find attached 2600001B_048_1.pdf {ADDRESS}"),
    row("300002", "[B1 Homes] Order 2600002B/048 file 2600002B_048_1.pdf"),
    row("300003", "file 2600003B_048_1.pdf", project="pln_10001"),
    row("300004", "file 2600004B_048_1.pdf", assignee="<user>"),
    row("300005", "no attachment here"),
)


class FakeDriver:
    """Records the calls the spike makes; returns `listing` from the read."""

    def __init__(self, listing: driver.NotePoolList, fail: Exception | None = None):
        self.listing = listing
        self.fail = fail
        self.calls: list[str] = []
        self.reads = 0

    @contextmanager
    def open_browser(self, *, headed: bool, slow_mo: int):
        self.calls.append(f"open_browser headed={headed} slow_mo={slow_mo}")
        yield "page"
        self.calls.append("closed")

    def go_home(self, page, base_url):
        self.calls.append("go_home")

    def login(self, guard, page, username, password):
        self.calls.append(f"login {username}")
        if self.fail:
            raise self.fail

    def open_note_pool(self, guard, page):
        self.calls.append("open_note_pool")
        return "panel"

    def set_note_pool_filters(self, guard, panel, pool_name):
        self.calls.append(f"filters {pool_name}")

    def read_note_pool(self, guard, panel):
        self.reads += 1
        self.calls.append("read")
        return self.listing


@pytest.fixture
def fake(monkeypatch):
    def install(listing=None, fail=None):
        listing = listing or driver.NotePoolList(rows=ROWS, total=5, pages=1)
        fake = FakeDriver(listing, fail)
        for name in (
            "open_browser",
            "go_home",
            "login",
            "open_note_pool",
            "set_note_pool_filters",
            "read_note_pool",
        ):
            monkeypatch.setattr(run.driver, name, getattr(fake, name))
        return fake

    return install


@pytest.fixture
def env(monkeypatch, tmp_path):
    for name in ("anthropic_api_key", "mysys_test_username", "mysys_test_password"):
        monkeypatch.delenv(f"PO_AGENT_{name.upper()}", raising=False)
    monkeypatch.setenv("PO_AGENT_MYSYS_TEST_USERNAME", "fake-user")
    monkeypatch.setenv("PO_AGENT_MYSYS_TEST_PASSWORD", "fake-password")
    previous = keyring.get_keyring()
    keyring.set_keyring(NullKeyring())
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(cli, "sweep_download_dirs", lambda: None)
    yield monkeypatch
    keyring.set_keyring(previous)


def stdout_lines(capsys) -> list[str]:
    return capsys.readouterr().out.splitlines()


def summary_of(lines: list[str]) -> dict:
    assert lines[-1].startswith("RUN_SUMMARY ")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def test_eligible_notes_keeps_the_order_and_the_internal_number():
    found = run.eligible_notes(ROWS, "test-body-filename", POOL)

    assert found == (
        run.EligibleNote(note_id="300001", internal_no="2600001B"),
        run.EligibleNote(note_id="300002", internal_no="2600002B"),
    )


def test_spike_logs_in_reads_the_list_once_and_prints_counts(env, fake, capsys):
    driver_ = fake()

    code = cli.main(["spike", "--site", "test", "--headed", "--slow-mo", "500"])

    lines = stdout_lines(capsys)
    assert code == 0
    assert driver_.calls == [
        "open_browser headed=True slow_mo=500",
        "go_home",
        "login fake-user",
        "open_note_pool",
        f"filters {POOL}",
        "read",
        "closed",
    ]
    assert driver_.reads == 1
    assert lines[:-1] == [
        "INFO  config loaded",
        "INFO  logged in",
        "INFO  note pool filters set",
        "INFO  note pool read: 5 rows, 2 eligible",
    ]
    summary = summary_of(lines)
    assert summary["mode"] == "spike"
    assert summary["seen"] == 5
    assert summary["eligible"] == 2
    assert summary["exit_code"] == 0


def test_spike_output_has_no_page_text(env, fake, capsys):
    fake()

    cli.main(["spike", "--site", "test"])

    out = "\n".join(stdout_lines(capsys))
    assert "Sample Lane" not in out
    assert "2600001B" not in out
    assert "300001" not in out
    assert "fake-password" not in out


def test_more_pages_adds_an_info_line(env, fake, capsys):
    fake(driver.NotePoolList(rows=ROWS, total=60, pages=2))

    cli.main(["spike", "--site", "test"])

    assert "INFO  note pool has more pages: only page 1 of 2 read" in stdout_lines(
        capsys
    )


def test_a_failed_login_is_alert_login_failed_exit_2(env, fake, capsys):
    driver_ = fake(fail=LoginFailed("login refused"))

    code = cli.main(["spike", "--site", "test"])

    lines = stdout_lines(capsys)
    assert code == 2
    assert lines[-2].startswith("ALERT LOGIN_FAILED ")
    assert summary_of(lines)["exit_code"] == 2
    assert driver_.calls[-1] == "closed"

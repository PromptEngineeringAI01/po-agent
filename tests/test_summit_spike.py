"""`spike --client summit` through the command and the run loop (task 9.11;
SPEC.md -> Client 2: Summit Home, Which Notes, The separate run).

The command, the run loop and the Summit client run for real; MySys is the
offline fake (tests/fakes/mysys.py) and the clock is replaced. The spike
logs in with Summit's own pair, sets Source and Unlocked, reads page 1 once
with its Source column and prints counts only: no Note is opened, nothing
is written, no NOTE line. A second page is ALERT MORE_PAGES, exit 1. The
run's start time decides the assignee rule (08:00 Perth). Secrets are fake
values in the environment; the committed client file with a fake mailbox
and sender, `enabled` on, in a temp config folder.
"""

import json
import tempfile
from datetime import UTC, datetime

import keyring
import pytest
from fakes.mysys import (
    SUMMIT_AGENT,
    SUMMIT_MAILBOX,
    SUMMIT_SENDER,
    FakeMySys,
    install,
    summit_row,
    summit_title,
)
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.core import controls, secrets
from po_agent.core.config import CONFIG_DIR
from po_agent.core.models import NotePoolFilters

AT_0759_PERTH = datetime(2026, 11, 24, 23, 59, tzinfo=UTC)  # Wednesday
AT_0800_PERTH = datetime(2026, 11, 25, 0, 0, tzinfo=UTC)
SPIKE = ["spike", "--site", "live", "--client", "summit"]
PERSON = "Fake Admin"

ROWS = (
    summit_row("462010"),  # eligible
    summit_row("462009", title=summit_title(word="ISSUED")),  # eligible
    summit_row("462008", assignee=PERSON),  # eligible only before 08:00 Perth
    summit_row("462007", assignee=SUMMIT_AGENT),  # agent-held
    summit_row("462006", project="pln_10001"),  # linked
    summit_row("462005", source=f"Fake Builder <{SUMMIT_SENDER}>"),  # display name
    summit_row(  # the PO twice
        "462004",
        title="Fake Builder - Lot 1 PO: 123456/020/01 - PO: 123456/020/01 - READY",
    ),
    summit_row("462003", title="Fake Builder Homes - Lot 1 - PO: 123456 - READY"),
)


@pytest.fixture
def env(monkeypatch, tmp_path):
    for name in secrets.SECRET_NAMES:
        monkeypatch.delenv(f"PO_AGENT_{name.upper()}", raising=False)
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_USERNAME", "fake-summit-user")
    monkeypatch.setenv("PO_AGENT_MYSYS_LIVE_SUMMIT_PASSWORD", "fake-summit-pass")
    previous = keyring.get_keyring()
    keyring.set_keyring(NullKeyring())
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")
    folder = tmp_path / "config"
    (folder / "clients").mkdir(parents=True)
    live = (CONFIG_DIR / "live.toml").read_text("utf-8")
    assert "\nenabled = true" in live
    (folder / "live.toml").write_text(live, "utf-8")
    summit = (CONFIG_DIR / "clients" / "summit.toml").read_text("utf-8")
    for old, new in (
        ("enabled = false", "enabled = true"),
        (
            'source_filter = "support@prompteng.com.au"',
            f'source_filter = "{SUMMIT_MAILBOX}"',
        ),
        ('sender = "noreply@summithomesgroup.com.au"', f'sender = "{SUMMIT_SENDER}"'),
    ):
        assert summit.count(old) == 1
        summit = summit.replace(old, new)
    (folder / "clients" / "summit.toml").write_text(summit, "utf-8")
    monkeypatch.setattr(cli, "CONFIG_DIR", folder)
    yield monkeypatch
    keyring.set_keyring(previous)


def fake_mysys(env, tmp_path, *, pages: int = 1) -> FakeMySys:
    fake = FakeMySys(notes={}, rows=ROWS, pool_pages=pages, logs_dir=tmp_path / "logs")
    return install(env, fake, booker=False)


def spike(env, capsys, at: datetime) -> tuple[int, list[str]]:
    env.setattr(controls, "now", lambda: at)
    code = cli.main(SPIKE)
    out = capsys.readouterr()
    assert out.err == ""
    return code, out.out.splitlines()


def summary_of(lines: list[str]) -> dict:
    assert lines[-1].startswith("RUN_SUMMARY ")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def test_the_spike_sets_summit_s_filters_reads_once_and_opens_no_note(
    env, capsys, tmp_path
):
    fake = fake_mysys(env, tmp_path)

    code, lines = spike(env, capsys, AT_0800_PERTH)

    assert code == 0
    assert fake.filters == [
        NotePoolFilters(pool=None, source=SUMMIT_MAILBOX, locked="Unlocked")
    ]
    assert fake.calls == [
        "open_browser",
        "go_home",
        "login",
        "open_note_pool",
        "filters",
        "read with source",
        "closed",
    ]
    assert lines[:-1] == [
        "INFO  config loaded",
        "INFO  logged in",
        "INFO  note pool filters set",
        "INFO  note pool read: 8 rows, 2 eligible",
    ]
    summary = summary_of(lines)
    assert (summary["mode"], summary["client"]) == ("spike", "summit")
    assert (summary["seen"], summary["eligible"], summary["exit_code"]) == (8, 2, 0)


def test_the_first_run_of_the_day_also_counts_a_person_s_note(env, capsys, tmp_path):
    fake_mysys(env, tmp_path)

    code, lines = spike(env, capsys, AT_0759_PERTH)

    assert code == 0
    assert "INFO  note pool read: 8 rows, 3 eligible" in lines
    assert summary_of(lines)["eligible"] == 3


def test_a_second_page_is_alert_more_pages_exit_1_after_the_counts(
    env, capsys, tmp_path
):
    fake_mysys(env, tmp_path, pages=2)

    code, lines = spike(env, capsys, AT_0800_PERTH)

    assert code == 1
    assert "INFO  note pool read: 8 rows, 2 eligible" in lines
    (alert,) = [line for line in lines if line.startswith("ALERT ")]
    assert alert.startswith("ALERT MORE_PAGES ")
    assert summary_of(lines)["exit_code"] == 1


def test_the_spike_prints_no_page_text_and_no_note_line(env, capsys, tmp_path):
    fake_mysys(env, tmp_path)

    _, lines = spike(env, capsys, AT_0759_PERTH)

    out = "\n".join(lines)
    assert not [line for line in lines if line.startswith("NOTE ")]
    for text in (
        "4620",
        "123456",
        SUMMIT_SENDER,
        "Fake Builder",
        PERSON,
        "fake-summit",
    ):
        assert text not in out

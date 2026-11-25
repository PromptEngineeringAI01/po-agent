"""`run --decide-only --client summit`: the peek (task 9.12; SPEC.md ->
Client 2: Summit Home, The peek, Decision checks; tasks/plan.md 9.12).

The command, the run loop, the Summit client, its decision engine and both
PDF readers run for real; MySys is the offline fake (tests/fakes/mysys.py)
and the clock is replaced. For each eligible row, newest first, up to
`max_peeks_per_run`, the run finds the Note again, opens it read-only and
reads its Assignee (the original assignee), Link to Project, attachments and
email body, downloads the PDF, runs both readers, does the project lookup
and decides. Nothing is assigned or written: every Note prints
`"outcome": "untouched"` with its skip reason, or `DECIDE_ONLY` for one that
would be booked. Business skips never alert; an UNEXPECTED_SCREEN stops the
run with its ALERT (7.2). The run cap (`max_notes_per_run`) counts bookings
only. Values are fake; expected values are written out from SPEC.md and the
plan.

What the guard-history test proves: the run loop's peek calls only the
driver's read steps. The fake records, for each step, the actions the real
step takes (`record_actions`), and its take and return record
their write actions and a call (`writes`), so a peek that reached either
fails. That the real read steps act with only those names is pinned by the
driver's own page tests and B1's seam 2 (9.12 second-model review).
"""

import json
import tempfile
from datetime import UTC, datetime

import keyring
import pytest
from fakes.mysys import (
    SUMMIT_AGENT,
    SUMMIT_BODY,
    SUMMIT_MAILBOX,
    SUMMIT_SENDER,
    FakeMySys,
    install,
    summit_lookup,
    summit_note,
    summit_pdf,
    summit_row,
    summit_titled,
)
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.core import controls, secrets
from po_agent.core.config import CONFIG_DIR

AT_0759_PERTH = datetime(2026, 11, 24, 23, 59, tzinfo=UTC)  # Wednesday
AT_0800_PERTH = datetime(2026, 11, 25, 0, 0, tzinfo=UTC)
DECIDE_ONLY = ["run", "--site", "live", "--client", "summit", "--decide-only"]
POOL = "PO Allocation Pool"  # a pool as an original assignee (Joey, 25 Nov 2026)
STAFF = "Fake Admin"  # a staff user as an original assignee

# The guard actions SPEC lets a Summit run take without a take: logging in,
# opening and filtering the Note Pool (step 0, as B1's), and per Note only
# "the read-only actions B1 already uses to find, open and download
# (open_note, refresh_note_pool, the Note ID search, download_attachment,
# the project search and opening clicks)" (SPEC.md -> The peek, step 4).
READ_ONLY = {
    "login_username",
    "login_password",
    "login_submit",
    "open_project_tab",
    "open_note_pool",
    "open_my_notes",
    "move_pointer_off_menu",
    "set_source_filter",
    "set_locked_filter",
    "set_pool_filter",
    "search_note_pool",
    "refresh_note_pool",
    "open_note",
    "download_attachment",
    "open_projects_subtab",
    "search_project",
    "submit_project_search",
    "open_project",
}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Fake Summit secrets, temp, logs, the trace and a config folder with
    the committed live profile and Summit client file (fake mailbox and
    sender, `enabled` on)."""
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
    live = (CONFIG_DIR / "live.toml").read_text("utf-8").splitlines()
    live = [line for line in live if not line.startswith("trace_dir")]
    live.append(f'trace_dir = "{(tmp_path / "trace").as_posix()}"')
    (folder / "live.toml").write_text("\n".join(live) + "\n", "utf-8")
    monkeypatch.setattr(cli, "CONFIG_DIR", folder)
    client_file(
        tmp_path,
        (
            'source_filter = "support@prompteng.com.au"',
            f'source_filter = "{SUMMIT_MAILBOX}"',
        ),
        ('sender = "noreply@summithomesgroup.com.au"', f'sender = "{SUMMIT_SENDER}"'),
    )
    yield monkeypatch
    keyring.set_keyring(previous)


def client_file(tmp_path, *changes: tuple[str, str]) -> None:
    """The committed Summit client file, `enabled` on, with `changes`."""
    path = tmp_path / "config" / "clients" / "summit.toml"
    if path.exists():
        text = path.read_text("utf-8")
    else:
        text = (CONFIG_DIR / "clients" / "summit.toml").read_text("utf-8")
        changes = (("enabled = false", "enabled = true"), *changes)
    for old, new in changes:
        assert text.count(old) == 1
        text = text.replace(old, new)
    path.write_text(text, "utf-8")


def fake_mysys(env, tmp_path, notes, titles=None, **kwargs) -> FakeMySys:
    """Each Note listed once, its Assignee as `notes` holds it, its title
    the Summit shape for its PO unless `titles` names another."""
    titles = titles or {}
    rows = tuple(
        summit_row(
            note_id,
            title=titles.get(note_id, summit_titled(f"{note.internal_no}/020/01")),
            assignee=note.assignee,
        )
        for note_id, note in notes.items()
    )
    fake = FakeMySys(
        notes=notes,
        rows=rows,
        logs_dir=tmp_path / "logs",
        record_actions=True,
        **kwargs,
    )
    return install(env, fake, booker=False)


def decide_only(env, capsys, at: datetime = AT_0800_PERTH) -> tuple[int, list[str]]:
    env.setattr(controls, "now", lambda: at)
    code = cli.main(DECIDE_ONLY)
    out = capsys.readouterr()
    assert out.err == ""
    return code, out.out.splitlines()


def notes_of(lines: list[str]) -> list[dict]:
    return [json.loads(x.removeprefix("NOTE  ")) for x in lines if x.startswith("NOTE")]


def alerts_of(lines: list[str]) -> list[tuple[str, dict]]:
    found = []
    for line in lines:
        if line.startswith("ALERT "):
            kind, _, body = line.removeprefix("ALERT ").partition(" ")
            found.append((kind, json.loads(body)))
    return found


def summary_of(lines: list[str]) -> dict:
    assert lines[-1].startswith("RUN_SUMMARY ")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def opened(fake: FakeMySys) -> list[str]:
    return [c.split()[1] for c in fake.calls if c.startswith("find_again ")]


def writes(fake: FakeMySys) -> list[str]:
    """Every fake call that assigns or writes in MySys."""
    return [c for c in fake.calls if c.split()[0] in ("take", "return")]


# --- the peek and DECIDE_ONLY -------------------------------------------------


def test_a_note_that_would_be_booked_is_untouched_decide_only(env, capsys, tmp_path):
    fake = fake_mysys(env, tmp_path, {"462001": summit_note()})

    code, lines = decide_only(env, capsys)

    assert code == 0
    assert notes_of(lines) == [
        {
            "note_id": "462001",
            "outcome": "untouched",
            "reason": "DECIDE_ONLY",
            "field": None,
            "po_number": "123456/020/01",
            "pln": "pln_20001",
            "task_id": None,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_aud": 0.0,
        }
    ]
    # Found again (All Pools, the exact ID) and opened once; every read of
    # the peek, the PDF downloaded, then the project lookup; no take, no
    # return, no booking.
    assert [c for c in fake.calls if c.endswith(" 462001")] == [
        "find_again 462001",
        "assignee 462001",
        "2a 462001",
        "names 462001",
        "download 462001",
        "body 462001",
        "lookup 462001",
    ]
    assert fake.notes["462001"].assignee == "---"
    assert not alerts_of(lines)
    summary = summary_of(lines)
    assert (summary["mode"], summary["client"]) == ("decide-only", "summit")
    assert (summary["eligible"], summary["booked"], summary["exit_code"]) == (1, 0, 0)


def test_each_business_skip_is_untouched_with_its_reason_and_no_alert(
    env, capsys, tmp_path
):
    notes = {
        "462006": summit_note("100006/020/01", linked=True),
        "462005": summit_note("100005/020/01", names=()),
        "462004": summit_note(
            "100004/020/01",
            names=("Fake Order 100004_020_01.pdf", "Fake Order 100004_020_01 b.pdf"),
        ),
        "462003": summit_note(
            "100003/020/01", pdf=summit_pdf("100003/020/01", item="SITE CLEAN")
        ),
        "462002": summit_note(
            "100002/020/01", pdf=summit_pdf("100002/020/09")
        ),  # the PDF's PO differs from the title's
        "462001": summit_note(
            "100001/020/01",
            lookup=summit_lookup("100001", company="Fake Other Builder"),
        ),
    }
    fake = fake_mysys(env, tmp_path, notes)

    code, lines = decide_only(env, capsys)

    assert code == 0
    assert [(n["note_id"], n["outcome"], n["reason"]) for n in notes_of(lines)] == [
        ("462006", "untouched", "NOTE_ALREADY_LINKED"),
        ("462005", "untouched", "NO_PDF"),
        ("462004", "untouched", "MULTIPLE_PDFS"),
        ("462003", "untouched", "NOT_COMPACTION"),
        ("462002", "untouched", "PO_MISMATCH"),
        ("462001", "untouched", "PROJECT_NOT_FOUND"),
    ]
    assert [n["po_number"] for n in notes_of(lines)] == [
        "100006/020/01",
        "100005/020/01",
        "100004/020/01",
        "100003/020/01",
        "100002/020/01",
        "100001/020/01",
    ]
    # Cheap first: only the Note whose PDF and title checks pass is looked
    # up in Projects.
    assert [c for c in fake.calls if c.startswith("lookup")] == ["lookup 462001"]
    assert not writes(fake)
    assert not alerts_of(lines)
    assert summary_of(lines)["exit_code"] == 0


@pytest.mark.parametrize("original", ["---", POOL, STAFF])
def test_the_first_run_of_the_day_peeks_any_original_assignee_and_leaves_it(
    original, env, capsys, tmp_path
):
    # Before 08:00 Perth any assignee but an agent account is eligible; the
    # peek reads it as it is and leaves the Note with it (9.13 returns a
    # taken Note to it).
    fake = fake_mysys(env, tmp_path, {"462001": summit_note(assignee=original)})

    code, lines = decide_only(env, capsys, AT_0759_PERTH)

    assert code == 0
    assert [(n["note_id"], n["reason"]) for n in notes_of(lines)] == [
        ("462001", "DECIDE_ONLY")
    ]
    assert "assignee 462001" in fake.calls
    assert fake.notes["462001"].assignee == original
    assert not writes(fake)


# --- the guard history: read-only actions only (SPEC.md -> The peek, step 4) ----


def test_the_guard_history_of_a_decide_only_run_holds_only_read_only_actions(
    env, capsys, tmp_path
):
    notes = {
        "462003": summit_note("100003/020/01"),  # would be booked
        "462002": summit_note("100002/020/01", names=()),  # NO_PDF
        "462001": summit_note(  # COMPANY_MISMATCH, after the lookup
            "100001/020/01",
            lookup=summit_lookup("100001", company="Summit New Homes"),
        ),
    }
    fake = fake_mysys(env, tmp_path, notes)

    code, lines = decide_only(env, capsys)

    assert code == 0
    assert [n["reason"] for n in notes_of(lines)] == [
        "DECIDE_ONLY",
        "NO_PDF",
        "COMPANY_MISMATCH",
    ]
    actions = {action for action, _ in fake.guard.history}
    assert actions <= READ_ONLY
    # Not vacuous: the Notes were opened, a PDF downloaded, a project
    # searched and opened.
    assert {"open_note", "download_attachment", "search_project", "open_project"} <= (
        actions
    )
    assert not writes(fake)


# --- caps -------------------------------------------------------------------


def test_the_peek_cap_stops_opening_notes(env, capsys, tmp_path):
    client_file(tmp_path, ("max_peeks_per_run = 10", "max_peeks_per_run = 2"))
    fake = fake_mysys(
        env,
        tmp_path,
        {
            "462003": summit_note("100003/020/01", names=()),
            "462002": summit_note("100002/020/01", names=()),
            "462001": summit_note("100001/020/01", names=()),
        },
    )

    code, lines = decide_only(env, capsys)

    assert code == 0
    assert opened(fake) == ["462003", "462002"]  # newest first, two opened
    assert "INFO  run cap reached: 1 notes left for the next run" in lines
    assert [n["note_id"] for n in notes_of(lines)] == ["462003", "462002"]


def test_the_run_cap_counts_bookings_only(env, capsys, tmp_path):
    # max_notes_per_run = 1 in the client file: three Notes that would be
    # booked are all peeked, since decide-only books none.
    fake = fake_mysys(
        env,
        tmp_path,
        {
            "462003": summit_note("100003/020/01"),
            "462002": summit_note("100002/020/01"),
            "462001": summit_note("100001/020/01"),
        },
    )

    code, lines = decide_only(env, capsys)

    assert code == 0
    assert opened(fake) == ["462003", "462002", "462001"]
    assert [n["reason"] for n in notes_of(lines)] == ["DECIDE_ONLY"] * 3
    assert not [line for line in lines if "run cap reached" in line]


# --- 7.2: an UNEXPECTED_SCREEN stops the run with its ALERT ---------------------


def test_when_every_eligible_note_is_unexpected_screen_the_first_alerts(
    env, capsys, tmp_path
):
    # The email body not found once (Summit's iframe rule) on both Notes: the
    # first stops the run, ALERT UNEXPECTED_SCREEN, exit 1; the second is
    # never opened.
    fake = fake_mysys(
        env,
        tmp_path,
        {
            "462002": summit_note("100002/020/01", fail_at="body"),
            "462001": summit_note("100001/020/01", fail_at="body"),
        },
    )

    code, lines = decide_only(env, capsys)

    assert code == 1
    assert opened(fake) == ["462002"]
    assert [(kind, alert["note_id"]) for kind, alert in alerts_of(lines)] == [
        ("UNEXPECTED_SCREEN", "462002")
    ]
    assert not notes_of(lines)
    assert not writes(fake)
    assert summary_of(lines)["exit_code"] == 1


def test_a_project_whose_client_internal_no_differs_is_unexpected_screen(
    env, capsys, tmp_path
):
    fake = fake_mysys(
        env,
        tmp_path,
        {
            "462002": summit_note(
                "100002/020/01", lookup=summit_lookup("100002", internal_no="100009")
            ),
            "462001": summit_note("100001/020/01"),
        },
    )

    code, lines = decide_only(env, capsys)

    assert code == 1
    assert opened(fake) == ["462002"]
    assert [(kind, alert["note_id"]) for kind, alert in alerts_of(lines)] == [
        ("UNEXPECTED_SCREEN", "462002")
    ]
    assert not writes(fake)


# --- output carries no page text ------------------------------------------------


def test_a_decide_only_run_prints_no_title_body_or_name(env, capsys, tmp_path):
    fake_mysys(env, tmp_path, {"462001": summit_note(assignee=STAFF)})

    _, lines = decide_only(env, capsys, AT_0759_PERTH)

    out = "\n".join(lines)
    for text in (
        "Fake Street",
        "Fake Builder Header",
        SUMMIT_BODY.splitlines()[-1],
        "Fake Order",
        STAFF,
        SUMMIT_SENDER,
        SUMMIT_AGENT,
        "fake-summit",
    ):
        assert text not in out

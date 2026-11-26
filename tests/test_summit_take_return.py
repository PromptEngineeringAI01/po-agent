# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""Summit's take and its return to the original assignee (task 9.13;
SPEC.md -> Client 2: The take and the booking, Return to the original
assignee; tasks/plan.md 9.13; decisions, 26 Nov 2026).

Two layers, values fake, expected values written out from SPEC.md:

- The return on a fake Note window (headless Chromium, offline, as
  tests/test_driver_note_window.py; screen-map rows 02, 15b, 26): the
  original assignee, whitespace around it stripped and matched exactly,
  goes back with one Assign - a user as that user with --Select Pool--, a
  pool as B1's return; a name in both lists or neither (`---` among them:
  Joey, 26 Nov 2026, "先留給 Agent 2") is never pressed for. Send Email is
  unticked and read back before the Assign. Tests never act on the page
  themselves (guard_check.py): what a click did shows through inline JS.
- The run loop that books, on the offline fake MySys (tests/fakes/mysys.py):
  on PROCEED the kill switch is read, the Note found again, its Assignee
  must still read the original (else `untouched` / NOTE_TAKEN), Agent 2
  takes it and Link to Project must still show; a Note taken and stopped
  before Submit goes back to its original assignee, or stays with Agent 2
  with ALERT UNEXPECTED_SCREEN "Note not returned". These call the run
  loop itself; the command is tests/test_summit_booking.py's (9.14).

B1's take and return are pinned unchanged by tests/test_driver_note_window.py,
tests/seam2/test_run_loop_offline.py and B1's seam 2 assignee cases.
"""

import argparse
import html
import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fakes.mysys import (
    PERSON,
    SUMMIT_AGENT,
    SUMMIT_MAILBOX,
    SUMMIT_SENDER,
    FakeMySys,
    install,
    summit_note,
    summit_row,
    summit_titled,
)
from playwright.sync_api import Browser, Page

from po_agent.core import controls, output, run, runlog
from po_agent.core.config import CONFIG_DIR, load_client, load_config
from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys import driver, wait
from po_agent.mysys.guard import ActionGuard
from po_agent.summit.client import SummitClient

NOTE_ID = "462001"
RUN_ID = "20261126T010203Z-abcd"
STAFF = "Fake Admin"  # a staff user as the original assignee
POOL = "PO Allocation Pool"  # a pool as the original assignee (Joey, 25 Nov 2026)
BOTH = "Fake Shared Name"  # a name in the user list and the pool list
USERS = (SUMMIT_AGENT, STAFF, BOTH)
POOLS = (POOL, BOTH)
CLOSE = '<div><span title="Close">close</span></div>'
# Before 08:00 Perth: any original assignee but an agent account is eligible.
AT_0759_PERTH = datetime(2026, 11, 24, 23, 59, tzinfo=UTC)
NOT_RETURNED = "Note not returned"


# --- the return on a fake Note window ------------------------------------------
# `browser` is tests/conftest.py's: one headless Chromium per module.


@pytest.fixture
def page(browser: Browser, monkeypatch) -> Iterator[Page]:
    monkeypatch.setattr(wait, "LOAD_TIMEOUT_MS", 2000)
    page = browser.new_page()
    page.set_default_timeout(2000)
    yield page
    page.close()


@pytest.fixture
def guard() -> ActionGuard:
    return ActionGuard()


@pytest.fixture
def log(guard, tmp_path) -> runlog.RunLog:
    return runlog.RunLog(RUN_ID, guard, directory=tmp_path)


def actions(guard: ActionGuard) -> list[str]:
    return [action for action, _ in guard.history]


def events(tmp_path) -> list[dict]:
    path = tmp_path / f"{RUN_ID}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def names(tmp_path) -> list[str]:
    """Each event as one name: the guard action, or read_back:<field>."""
    out = []
    for event in events(tmp_path):
        if event["event"] == "guard_action":
            out.append(event["action"])
        elif "field" in event:
            out.append(f"read_back:{event['field']}")
        else:
            out.append(event["event"])
    return out


def options(texts: tuple[str, ...]) -> str:
    return "".join(f"<option>{html.escape(text)}</option>" for text in texts)


def note_page(
    *,
    users: tuple[str, ...] = USERS,
    pools: tuple[str, ...] = POOLS,
    reticks_email: bool = False,
) -> str:
    """A Summit Note window reopened while Agent 2 holds it: the user list
    pre-selects the agent, Send Email ticked (row 02). Assign records the
    two lists' values at the click and whether the box was ticked, then
    the Assignee, a new "User Assigned" log line and Status Pending."""
    retick = "document.getElementById('email').checked = true;" if reticks_email else ""
    user_options = options(users).replace(
        f"<option>{html.escape(SUMMIT_AGENT)}</option>",
        f"<option selected>{html.escape(SUMMIT_AGENT)}</option>",
    )
    return f"""
<div><div>
  <h3>Note {NOTE_ID} - created on 25 Nov 2026</h3>
  <div>
    <h3>Fake Builder Homes - PO: 123456/020/01 - READY</h3>
    <div><strong>Assignee:</strong> <span id="assignee">{SUMMIT_AGENT}</span> <button>Unlink</button></div>
    <div role="group" aria-label="Status buttons">
      <button disabled>Pending</button><button>Solved</button><button>Discard</button>
    </div>
    <select id="user" onchange="{retick}"><option>--Select User--</option>{user_options}</select>
    <select id="pool"><option selected>--Select Pool--</option>{options(pools)}</select>
    <button onclick="assign()">Assign</button>
    <span><input type="checkbox" id="email" checked aria-label="Send Email Notification"> Send Email Notification</span>
    <button>Link to Project</button>
    <ul><li><strong>Status:</strong> <span id="status">Pending</span></li></ul>
    <div><h4>Logs</h4><ul id="logs">
      <li><em>26 Nov 2026 08:01 User Assigned: (By {SUMMIT_AGENT})</em> From <strong>{STAFF}</strong> to <strong>{SUMMIT_AGENT}</strong><hr></li>
    </ul></div>
  </div>
</div>{CLOSE}</div>
<script>
document.body.dataset.assigns = '0';
function assign() {{
  document.body.dataset.assigns = String(Number(document.body.dataset.assigns) + 1);
  if (document.getElementById('email').checked) document.body.dataset.emailed = 'yes';
  const user = document.getElementById('user'), pool = document.getElementById('pool');
  document.body.dataset.assigned = user.value + '|' + pool.value;
  const who = user.value !== '--Select User--' ? user.value : pool.value;
  const was = document.getElementById('assignee').textContent;
  setTimeout(() => {{
    document.getElementById('assignee').textContent = who;
    const li = document.createElement('li');
    li.innerHTML = '<em>26 Nov 2026 09:00 User Assigned: (By {SUMMIT_AGENT})</em> From <strong>' + was + '</strong> to <strong>' + who + '</strong><hr>';
    document.getElementById('logs').prepend(li);
    user.selectedIndex = 0; pool.selectedIndex = 0;
  }}, 200);
}}
</script>"""


def window_of(page: Page, content: str):
    page.set_content(content)
    return driver.note_window(page, NOTE_ID)


def body_data(page: Page, name: str) -> str | None:
    return page.locator("body").get_attribute(f"data-{name}")


@pytest.mark.parametrize(
    ("original", "users", "pools", "assigned", "assignee"),
    [
        # A user: user list = that user, pool list --Select Pool--.
        (STAFF, USERS, POOLS, f"{STAFF}|--Select Pool--", STAFF),
        # A pool: B1's return, --Select User-- and that pool.
        (POOL, USERS, POOLS, f"--Select User--|{POOL}", POOL),
        # Whitespace around the name read is stripped.
        (f"  {STAFF}\n", USERS, POOLS, f"{STAFF}|--Select Pool--", STAFF),
    ],
)
def test_the_return_is_one_assign_to_the_original_assignee_s_list(
    original, users, pools, assigned, assignee, page, guard, log, tmp_path
):
    window = window_of(page, note_page(users=users, pools=pools))

    driver.return_to_assignee(guard, window, SUMMIT_AGENT, original, log, NOTE_ID)

    assert body_data(page, "assigned") == assigned
    assert body_data(page, "assigns") == "1"
    assert body_data(page, "emailed") is None
    assert driver.read_assignee(window) == assignee
    assert actions(guard) == [
        "untick_send_email_notification",
        "select_note_user",
        "select_note_pool",
        "assign_note",
    ]
    order = names(tmp_path)
    # Send Email read back unticked after the last change, before Assign.
    assert order.index("email_notification_unticked") > order.index("select_note_pool")
    assert order.index("email_notification_unticked") < order.index("assign_note")
    assert {"read_back:assignee", "read_back:log_line"} <= set(order)
    assert {e["step"] for e in events(tmp_path)} == {"return"}


@pytest.mark.parametrize(
    "original",
    [
        BOTH,  # in both lists
        "---",  # unassigned before the take: neither (decisions, 26 Nov 2026)
        "fake admin",  # case differs from a user: neither, never a near match
        "Fake Adm",  # a part of a user's name: neither
        "--Select Pool--",  # a placeholder is no name: Assign would do nothing (S6)
        "--Select User--",
    ],
)
def test_a_name_in_both_lists_or_neither_is_not_returned_and_nothing_is_pressed(
    original, page, guard, log
):
    window = window_of(page, note_page())

    with pytest.raises(UnexpectedScreen) as stopped:
        driver.return_to_assignee(guard, window, SUMMIT_AGENT, original, log, NOTE_ID)

    assert stopped.value.detail == NOT_RETURNED
    assert (stopped.value.note_id, stopped.value.step) == (NOTE_ID, "return")
    assert guard.history == []
    assert body_data(page, "assigns") == "0"
    assert driver.read_assignee(window) == SUMMIT_AGENT


def test_send_email_ticked_again_before_the_return_s_assign_stops_without_assigning(
    page, guard, log, tmp_path
):
    window = window_of(page, note_page(reticks_email=True))

    with pytest.raises(UnexpectedScreen):
        driver.return_to_assignee(guard, window, SUMMIT_AGENT, STAFF, log, NOTE_ID)

    assert "assign_note" not in actions(guard)
    assert body_data(page, "assigns") == "0"
    unticked = [
        (e["step"], e["ok"])
        for e in events(tmp_path)
        if e["event"] == "email_notification_unticked"
    ]
    assert unticked == [("return", False)]


def test_a_dashes_original_is_never_returned_even_when_a_list_offers_dashes(
    page, guard, log
):
    # Joey, 26 Nov 2026 ("好，先留給 Agent 2"): `---` stays with Agent 2
    # whatever the page's lists hold (9.13 second-model review, Nit 2).
    window = window_of(page, note_page(users=(SUMMIT_AGENT, "---", STAFF)))

    with pytest.raises(UnexpectedScreen) as stopped:
        driver.return_to_assignee(guard, window, SUMMIT_AGENT, " --- ", log, NOTE_ID)

    assert stopped.value.detail == NOT_RETURNED
    assert guard.history == []
    assert body_data(page, "assigns") == "0"


# --- the run loop that books: the take and the return ---------------------------


@pytest.fixture
def folder(tmp_path):
    """A config folder: the committed live profile (its trace off) and the
    committed Summit client file, `enabled` on, with the fake mailbox and
    sender."""
    folder = tmp_path / "config"
    (folder / "clients").mkdir(parents=True)
    live = (CONFIG_DIR / "live.toml").read_text("utf-8").splitlines()
    live = [line for line in live if not line.startswith("trace_dir")]
    live.append(f'trace_dir = "{(tmp_path / "trace").as_posix()}"')
    (folder / "live.toml").write_text("\n".join(live) + "\n", "utf-8")
    text = (CONFIG_DIR / "clients" / "summit.toml").read_text("utf-8")
    for old, new in (
        ("enabled = false", "enabled = true"),
        (
            'source_filter = "support@prompteng.com.au"',
            f'source_filter = "{SUMMIT_MAILBOX}"',
        ),
        ('sender = "noreply@summithomesgroup.com.au"', f'sender = "{SUMMIT_SENDER}"'),
    ):
        assert text.count(old) == 1
        text = text.replace(old, new)
    (folder / "clients" / "summit.toml").write_text(text, "utf-8")
    return folder


def fake_mysys(monkeypatch, folder, note) -> FakeMySys:
    """One eligible Summit Note, its window's user and pool lists USERS and
    POOLS; the kill switch is the client file's."""
    row = summit_row(NOTE_ID, title=summit_titled(), assignee=note.assignee)
    fake = FakeMySys(
        notes={NOTE_ID: note},
        rows=(row,),
        config_dir=folder,
        kill_file="clients/summit.toml",
        note_users=USERS,
        note_pools=POOLS,
    )
    return install(monkeypatch, fake, summit=True)


def book_run(monkeypatch, folder, tmp_path) -> int:
    """Summit's run that books, from the run loop (the command is
    tests/test_summit_booking.py's), at 07:59 Perth."""
    monkeypatch.setattr(controls, "now", lambda: AT_0759_PERTH)
    config = load_config("live", folder)
    profile = load_client("summit", "live", folder)
    _, username, password = run.account(config, profile)
    return run.book_run(
        config,
        SummitClient(config, profile, AT_0759_PERTH),
        {username: "fake-summit-user", password: "fake-summit-pass"},
        argparse.Namespace(headed=False, slow_mo=0),
        output.RunSummary(run_id=RUN_ID, site="live", client="summit", mode="run"),
        tmp_path / "downloads",
        None,
        folder,
        None,
        profile,
    )


def notes_of(lines: list[str]) -> list[dict]:
    return [json.loads(x.removeprefix("NOTE  ")) for x in lines if x.startswith("NOTE")]


def after_peek(fake: FakeMySys) -> list[str]:
    """The fake calls from the peek's last read (the project lookup) on."""
    return fake.calls[fake.calls.index(f"lookup {NOTE_ID}") :]


@pytest.mark.parametrize("original", [STAFF, POOL, "---"])
def test_a_proceed_note_still_with_its_original_assignee_is_taken_by_agent_2(
    original, monkeypatch, folder, tmp_path
):
    # What follows the take (W1-W5, 9.14) is tests/test_summit_booking.py's:
    # only the take is pinned here.
    fake = fake_mysys(monkeypatch, folder, summit_note(assignee=original))

    book_run(monkeypatch, folder, tmp_path)

    assert after_peek(fake)[:5] == [
        f"lookup {NOTE_ID}",
        f"find_again {NOTE_ID}",  # found again for the take
        f"assignee {NOTE_ID}",  # still the original
        f"take {NOTE_ID}",
        f"2a {NOTE_ID}",  # Link to Project still shows
    ]
    assert fake.notes[NOTE_ID].taken == 1


def test_the_take_refuses_a_note_whose_assignee_changed_since_the_peek(
    monkeypatch, folder, tmp_path, capsys
):
    # A person takes it between the peek and the take (found again: #2).
    note = summit_note(assignee=STAFF, person_takes_at="find_again#2")
    fake = fake_mysys(monkeypatch, folder, note)

    code = book_run(monkeypatch, folder, tmp_path)

    assert code == 0
    assert notes_of(capsys.readouterr().out.splitlines()) == [
        {
            "note_id": NOTE_ID,
            "outcome": "untouched",
            "reason": "NOTE_TAKEN",
            "field": None,
            "po_number": "123456/020/01",
            "pln": None,
            "task_id": None,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_aud": 0.0,
        }
    ]
    assert fake.notes[NOTE_ID].taken == 0
    assert fake.notes[NOTE_ID].assignee == PERSON
    assert not [c for c in fake.calls if c.startswith("return")]


def test_the_kill_switch_read_before_the_take_stops_with_nothing_taken(
    monkeypatch, folder, tmp_path, capsys
):
    # `enabled` turned off in the client file during the peek's last read.
    note = summit_note(assignee=STAFF, kill_at="lookup")
    fake = fake_mysys(monkeypatch, folder, note)

    code = book_run(monkeypatch, folder, tmp_path)

    assert code == 0
    assert "kill switch on: run stopped" in capsys.readouterr().out
    assert after_peek(fake) == [f"lookup {NOTE_ID}", "closed"]
    assert fake.notes[NOTE_ID].assignee == STAFF


@pytest.mark.parametrize("original", [STAFF, POOL, f" {STAFF} "])
def test_a_note_taken_and_stopped_before_submit_goes_back_to_its_original_assignee(
    original, monkeypatch, folder, tmp_path
):
    # A person links the Note during the take: Link to Project no longer
    # shows after it, a stop before Submit.
    note = summit_note(assignee=original, link_at="take")
    fake = fake_mysys(monkeypatch, folder, note)

    with pytest.raises(UnexpectedScreen) as stopped:
        book_run(monkeypatch, folder, tmp_path)

    assert NOT_RETURNED not in str(stopped.value)
    assert stopped.value.note_id == NOTE_ID
    assert [c for c in fake.calls if c.startswith("return")] == [f"return {NOTE_ID}"]
    assert fake.notes[NOTE_ID].assignee == original.strip()
    assert not {"reopen", "form", "submit"} & {c.split()[0] for c in fake.calls}


@pytest.mark.parametrize("original", ["---", BOTH])
def test_a_note_whose_original_assignee_is_in_both_lists_or_neither_stays_with_agent_2(
    original, monkeypatch, folder, tmp_path
):
    # `---` included: Joey, 26 Nov 2026, "先留給 Agent 2". The stale-Note stop
    # holds later runs until a person moves it.
    note = summit_note(assignee=original, link_at="take")
    fake = fake_mysys(monkeypatch, folder, note)

    with pytest.raises(UnexpectedScreen) as stopped:
        book_run(monkeypatch, folder, tmp_path)

    assert stopped.value.detail == f"run stopped; {NOT_RETURNED}"
    assert (stopped.value.alert_kind, stopped.value.exit_code) == (
        "UNEXPECTED_SCREEN",
        1,
    )
    assert stopped.value.note_id == NOTE_ID
    assert fake.notes[NOTE_ID].assignee == SUMMIT_AGENT


def test_a_taken_proceed_is_booked_and_never_returned(monkeypatch, folder, tmp_path):
    # Replaces 9.13's interim pin (a taken PROCEED stopped before any booker
    # step and went back): from 9.14 the booking follows the take
    # (decisions, 26 Nov 2026, Summit booking).
    fake = fake_mysys(monkeypatch, folder, summit_note(assignee=STAFF))

    code = book_run(monkeypatch, folder, tmp_path)

    assert code == 0
    steps = [c.split()[0] for c in after_peek(fake)]
    assert steps[steps.index("take") :][:4] == ["take", "2a", "check", "reopen"]
    assert {"submit", "solved", "gone"} <= set(steps)
    assert fake.notes[NOTE_ID].taken == 1
    assert fake.notes[NOTE_ID].assignee == SUMMIT_AGENT
    assert not [c for c in fake.calls if c.startswith("return")]

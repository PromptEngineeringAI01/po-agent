# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""Tests for the Note-window steps in mysys/driver.py (task 3.1).

Headless Chromium on a local fake of the test site's Note window, offline: no
site is touched. The fake follows docs/screen-map.md rows 02-04, 15b and 26:
heading "Note <id> - ...", the user and pool lists found by their
placeholder options, Send Email Notification ticked when the window opens,
and the Logs list (an h4 "Logs" and one list item per line, newest first:
"<date> User Assigned: (By <user>)" in an <em>, then "From <x> to <y>").
The reload test loads a fake login or app page as a data: URL. Values are
fake. Tests never act on the page themselves (guard_check.py): what a click did shows up through inline JS.
"""

import json
from collections.abc import Iterator
from urllib.parse import quote

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from po_agent.b1.models import NotePoolRow
from po_agent.core import runlog
from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys import driver
from po_agent.mysys.guard import ALLOWLIST, ActionGuard, Kind

AGENT = "Agent 1 (MySys Only)"
POOL = "Agent Pool"
NOTE_ID = "300001"
RUN_ID = "20261102T010203Z-abcd"
CLOSE = '<div><span title="Close">close</span></div>'
USER = "fake-user"
PASSWORD = "fake-Password-42"


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser, monkeypatch) -> Iterator[Page]:
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 2000)
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
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def names(tmp_path) -> list[str]:
    """Each event as one name: the guard action, or event:field."""
    out = []
    for event in events(tmp_path):
        if event["event"] == "guard_action":
            out.append(event["action"])
        elif "field" in event:
            out.append(f"read_back:{event['field']}")
        else:
            out.append(event["event"])
    return out


def note_page(
    *,
    assignee: str = POOL,
    linked: str = "no",
    adds_log_line: bool = True,
    status_after: str = "Pending",
    reticks_email: bool = False,
) -> str:
    """The Note window as it opens. linked: "no" (Link to Project), "yes"
    (the project button and Change Project), "unclear" (neither)."""
    link = {
        "no": "<button>Link to Project</button>",
        "yes": "<button>pln_10001</button><button>Change Project</button>",
        "unclear": "",
    }[linked]
    retick = "document.getElementById('email').checked = true;" if reticks_email else ""
    return f"""
<div><div>
  <h3>Note {NOTE_ID} - created on 12 Oct 2026</h3>
  <div>
    <h3>[B1 Homes] Order 2600001B/048</h3>
    <div><strong>Assignee:</strong> <span id="assignee">{assignee}</span> <button>Unlink</button></div>
    <div role="group" aria-label="Status buttons">
      <button disabled>Pending</button><button>Solved</button><button>Discard</button>
    </div>
    <select id="user" onchange="{retick}"><option>--Select User--</option><option selected>{AGENT}</option><option>Fake Person</option></select>
    <select id="pool"><option selected>--Select Pool--</option><option>{POOL}</option></select>
    <button onclick="assign()">Assign</button>
    <span><input type="checkbox" id="email" checked aria-label="Send Email Notification"> Send Email Notification</span>
    {link}
    <ul><li><strong>Status:</strong> <span id="status">Pending</span></li></ul>
    <div><h4>Logs</h4><ul id="logs">
      <li><em>12 Oct 2026 13:28 User Assigned: (By Fake Person)</em> From <strong>Fake Person</strong> to <strong>{assignee}</strong><hr></li>
    </ul></div>
  </div>
</div>{CLOSE}</div>
<script>
document.body.dataset.assigns = '0';
function assign() {{
  document.body.dataset.assigns = String(Number(document.body.dataset.assigns) + 1);
  if (document.getElementById('email').checked) document.body.dataset.emailed = 'yes';
  const user = document.getElementById('user'), pool = document.getElementById('pool');
  const who = user.value !== '--Select User--' ? user.value : pool.value;
  const was = document.getElementById('assignee').textContent;
  setTimeout(() => {{
    document.getElementById('assignee').textContent = who;
    document.getElementById('status').textContent = {json.dumps(status_after)};
    if ({json.dumps(adds_log_line)}) {{
      const li = document.createElement('li');
      li.innerHTML = '<em>02 Nov 2026 09:00 User Assigned: (By {AGENT})</em> From <strong>' + was + '</strong> to <strong>' + who + '</strong><hr>';
      document.getElementById('logs').prepend(li);
    }}
    user.selectedIndex = 0; pool.selectedIndex = 0;
  }}, 200);
}}
</script>"""


def window_of(page: Page, html: str):
    page.set_content(html)
    return driver.note_window(page, NOTE_ID)


def body_data(page: Page, name: str) -> str | None:
    return page.locator("body").get_attribute(f"data-{name}")


# --- Assign to agent (step 2, rows 03-04) -----------------------------------------


def test_take_note_unticks_email_assigns_once_and_reads_back(
    page, guard, log, tmp_path
):
    window = window_of(page, note_page())

    driver.take_note(guard, window, AGENT, log, NOTE_ID)

    assert driver.read_assignee(window) == AGENT
    assert body_data(page, "emailed") is None
    assert body_data(page, "assigns") == "1"
    assert actions(guard) == [
        "untick_send_email_notification",
        "select_note_user",
        "assign_note",
    ]
    order = names(tmp_path)
    # The read-back unticked comes after the last change before Assign.
    assert order.index("email_notification_unticked") > order.index("select_note_user")
    assert order.index("email_notification_unticked") < order.index("assign_note")
    assert {"read_back:assignee", "read_back:log_line"} <= set(order)
    assert {e["note_id"] for e in events(tmp_path)} == {NOTE_ID}
    assert {e["step"] for e in events(tmp_path)} == {"2"}


def test_take_note_with_no_new_log_line_stops(page, guard, log):
    window = window_of(page, note_page(adds_log_line=False))
    with pytest.raises(UnexpectedScreen):
        driver.take_note(guard, window, AGENT, log, NOTE_ID)


def test_email_ticked_again_before_assign_stops_without_assigning(page, guard, log):
    window = window_of(page, note_page(reticks_email=True))
    with pytest.raises(UnexpectedScreen):
        driver.take_note(guard, window, AGENT, log, NOTE_ID)
    assert "assign_note" not in actions(guard)
    assert body_data(page, "assigns") == "0"


# --- Step 2a --------------------------------------------------------------------


@pytest.mark.parametrize("linked, unlinked", [("no", True), ("yes", False)])
def test_step_2a_reads_link_to_project_and_presses_nothing(
    page, guard, log, tmp_path, linked, unlinked
):
    window = window_of(page, note_page(assignee=AGENT, linked=linked))
    assert driver.is_unlinked(window, log, NOTE_ID) is unlinked
    assert guard.history == []
    assert [(e["event"], e.get("field"), e["step"]) for e in events(tmp_path)] == [
        ("read_back", "link_to_project", "2a")
    ]


def test_step_2a_with_neither_link_nor_project_is_an_unexpected_screen(page, log):
    window = window_of(page, note_page(assignee=AGENT, linked="unclear"))
    with pytest.raises(UnexpectedScreen):
        driver.is_unlinked(window, log, NOTE_ID)


# --- Assign to pool (row 15b) ----------------------------------------------------


def test_return_note_is_one_assign_from_a_fresh_window_and_reads_back(
    page, guard, log, tmp_path
):
    # A reopened window: the user list pre-selects the agent, email ticked.
    window = window_of(page, note_page(assignee=AGENT))

    driver.return_note(guard, window, AGENT, POOL, log, NOTE_ID)

    assert driver.read_assignee(window) == POOL
    assert driver.read_status(window) == "Pending"
    assert body_data(page, "emailed") is None
    assert body_data(page, "assigns") == "1"
    assert actions(guard) == [
        "untick_send_email_notification",
        "select_note_user",
        "select_note_pool",
        "assign_note",
    ]
    assert not [a for a in actions(guard) if ALLOWLIST[a] == Kind.PRESS]
    order = names(tmp_path)
    assert order.index("email_notification_unticked") > order.index("select_note_pool")
    assert order.index("email_notification_unticked") < order.index("assign_note")
    assert {"read_back:assignee", "read_back:log_line", "read_back:status"} <= set(
        order
    )
    assert {e["step"] for e in events(tmp_path)} == {"return"}


def test_return_note_whose_status_is_not_pending_stops(page, guard, log):
    window = window_of(page, note_page(assignee=AGENT, status_after="Solved"))
    with pytest.raises(UnexpectedScreen):
        driver.return_note(guard, window, AGENT, POOL, log, NOTE_ID)


def test_return_note_with_no_new_log_line_stops(page, guard, log):
    window = window_of(page, note_page(assignee=AGENT, adds_log_line=False))
    with pytest.raises(UnexpectedScreen):
        driver.return_note(guard, window, AGENT, POOL, log, NOTE_ID)


# --- Reload between Notes (rows 25, 27) ------------------------------------------

LOGIN_PAGE = """
<title>Test Prompt Engineering - Login</title>
<form onsubmit="return false">
  <input aria-label="Username"><input aria-label="Password" type="password">
  <button onclick="setTimeout(() => {{ document.body.innerHTML = '{app}'; }}, 200)">Log in</button>
</form>
"""
APP_PAGE = "<ul><li><span>Project</span></li></ul>"


@pytest.mark.parametrize("logged_out", [True, False])
def test_reload_home_logs_in_again_only_if_the_login_page_shows(
    page, guard, logged_out
):
    html = LOGIN_PAGE.format(app=APP_PAGE) if logged_out else APP_PAGE
    # The fake page as a data: URL: no request leaves the test.
    base_url = "data:text/html," + quote(html)

    driver.reload_home(guard, page, base_url, USER, PASSWORD)

    logins = ["login_username", "login_password", "login_submit"]
    assert actions(guard) == (logins if logged_out else [])
    assert page.locator("li").get_by_text("Project", exact=True).is_visible()


# --- Finding a Note again: the ID cell must equal the Note ID ---------------------


def listing(*note_ids: str) -> driver.NotePoolList:
    rows = tuple(
        NotePoolRow(note_id=n, subject_note="fake", project="---", assignee=POOL)
        for n in note_ids
    )
    return driver.NotePoolList(rows=rows, total=len(rows), pages=1)


@pytest.mark.parametrize(
    "note_ids, found",
    [
        (("300001",), True),
        (("300001", "3000012"), True),  # the search matches substrings
        (("3000012",), False),
        (("1300001",), False),
        ((), False),
        (("300001", "300001"), False),  # the same row twice: not one
    ],
)
def test_only_a_row_whose_id_equals_the_note_id_counts(note_ids, found):
    assert driver.found_once(listing(*note_ids), NOTE_ID) is found

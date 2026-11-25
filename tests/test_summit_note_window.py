# ruff: noqa: E501 - the fake page HTML reads better unwrapped
"""A Summit Note window read by the peek (task 9.12; SPEC.md -> Client 2:
Summit Home, The peek, and The take and the booking: Email body).

Headless Chromium on a local fake of a live Summit email Note's window,
offline: no site is touched. Shapes from Joey's live screenshots (25 Nov
2026, kept in private/summit/; shapes only, values fake): the heading
"Note <id> - ...", "Assignee:" with a red Unlink (trash) button beside it
even on an unlinked Note, both Assign lists at their placeholders, Send
Email Notification ticked, Link to Project, one "Download document" link
whose file name has "_" in the PO, and the email body as one iframe: a
header table, the PO details table, one line of text and a Disclaimer.

Summit's body rule: exactly one iframe in the Note window whose body text
is not empty, waited for up to the load wait (15 s; 2 s here); still empty
after it, none, or more than one -> UNEXPECTED_SCREEN; its text with its
line breaks. B1 keeps "ends with the file name" (tests/test_booking.py).
Tests never act on the page; the reads click nothing.
"""

import html
from collections.abc import Iterator
from datetime import UTC, datetime
from urllib.parse import quote

import pytest
from playwright.sync_api import Browser, Page

from po_agent.core import runlog
from po_agent.core.config import CONFIG_DIR, load_client, load_config
from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard
from po_agent.summit.client import SummitClient

NOTE_ID = "462001"
FILE = "Fake Order 123456_020_01.pdf"
RUN_ID = "20261125T000000Z-abcd"
# The long fake email body: a header table, the PO details table, one line
# of text and a Disclaimer.
EMAIL = (
    "<table><tr><td>Fake Builder Header</td></tr></table>"
    "<table><tr><td>Purchase Order</td><td>123456/020/01</td></tr>"
    "<tr><td>Site</td><td>Lot 1 Fake Street</td></tr></table>"
    "<div>Please find the fake purchase order attached.</div>"
    "<div>Disclaimer: fake disclaimer text.</div>"
)
# Its text as the Note's task Note: line breaks kept, table cells apart.
EMAIL_TEXT = (
    "Fake Builder Header\n"
    "Purchase Order\t123456/020/01\n"
    "Site\tLot 1 Fake Street\n"
    "Please find the fake purchase order attached.\n"
    "Disclaimer: fake disclaimer text."
)


@pytest.fixture
def page(browser: Browser, short_waits) -> Iterator[Page]:
    # `browser` is tests/conftest.py's; short_waits: the 15 s load wait is
    # 2 s here (tests/fakes/browser.py).
    page = browser.new_page()
    page.set_default_timeout(2000)
    yield page
    page.close()


def body_rule():
    """Summit's body rule, as its client gives it to the run loop."""
    client = SummitClient(
        load_config("live", CONFIG_DIR),
        load_client("summit", "live", CONFIG_DIR),
        datetime(2026, 11, 25, 2, 0, tzinfo=UTC),
    )
    return client.body_rule(FILE)


def iframe(content: str) -> str:
    return f'<div><iframe srcdoc="{html.escape(content)}" style="width:100%;height:400px"></iframe></div>'


def late(content: str, ms: int) -> str:
    """An empty iframe whose document arrives `ms` after the window shows
    (live: the iframe's src loads after the window)."""
    return iframe("") + (
        "<script>setTimeout(() => {"
        f" document.querySelectorAll('iframe')[0].srcdoc = {content!r}; }}, {ms});</script>"
    )


def summit_note_page(assignee: str = "---", body: str = iframe(EMAIL)) -> str:
    href = f"download.php?file_name={quote(FILE)}"
    return f"""
<div><div>
  <h3>Note {NOTE_ID} - created on 25 Nov 2026</h3>
  <div>
    <div><strong>Assignee:</strong> {html.escape(assignee)} <button title="Unlink" style="color:red"><i class="fa fa-trash"></i></button></div>
    <div role="group" aria-label="Status buttons">
      <button disabled>Pending</button><button>Solved</button><button>Discard</button>
    </div>
    <select><option selected>--Select User--</option><option>Agent 2 (Summit Homes)</option><option>Fake Admin</option></select>
    <select><option selected>--Select Pool--</option><option>PO Allocation Pool</option></select>
    <button>Assign</button>
    <span><input type="checkbox" checked aria-label="Send Email Notification"> Send Email Notification</span>
    <button>Link to Project</button>
    <div><a href="{href}">Download document</a> <span>{FILE}</span></div>
    {body}
  </div>
</div><div><span title="Close">close</span></div></div>
"""


def window(page: Page, content: str):
    page.set_content(content)
    return driver.note_window(page, NOTE_ID)


# --- the email body ---------------------------------------------------------------


def test_the_one_iframe_s_long_body_is_read_with_its_line_breaks(page):
    assert driver.note_body(window(page, summit_note_page()), body_rule()) == EMAIL_TEXT


def test_an_iframe_that_loads_within_the_wait_is_read(page):
    # 1.5 s into the 2 s wait (live: 14 s into 15 s).
    note = window(page, summit_note_page(body=late(EMAIL, 1500)))

    assert driver.note_body(note, body_rule()) == EMAIL_TEXT


def test_an_iframe_still_empty_after_the_wait_is_unexpected_screen(page):
    # Arrives at 3 s, after the 2 s wait (live: after 15 s).
    note = window(page, summit_note_page(body=late(EMAIL, 3000)))

    with pytest.raises(UnexpectedScreen) as caught:
        driver.note_body(note, body_rule())
    assert "Fake" not in str(caught.value)


def test_no_iframe_is_unexpected_screen_even_with_a_pre_body(page):
    # Summit's body is the email iframe only: B1's <pre> is not taken.
    note = window(page, summit_note_page(body="<pre>Fake body in a pre</pre>"))

    with pytest.raises(UnexpectedScreen):
        driver.note_body(note, body_rule())


def test_two_non_empty_iframes_are_unexpected_screen(page):
    note = window(
        page, summit_note_page(body=iframe(EMAIL) + iframe("<div>Other</div>"))
    )

    with pytest.raises(UnexpectedScreen):
        driver.note_body(note, body_rule())


def test_a_second_iframe_that_fills_during_the_wait_is_unexpected_screen(page):
    # Read once every iframe has its text: one filling late still counts.
    second = iframe("") + (
        "<script>setTimeout(() => {"
        " document.querySelectorAll('iframe')[1].srcdoc = '<div>Other</div>'; }, 800);</script>"
    )
    note = window(page, summit_note_page(body=iframe(EMAIL) + second))

    with pytest.raises(UnexpectedScreen):
        driver.note_body(note, body_rule())


def test_one_non_empty_iframe_beside_one_that_stays_empty_is_the_body(page):
    # "Exactly one iframe whose body text is not empty" (SPEC).
    note = window(page, summit_note_page(body=iframe(EMAIL) + iframe("")))

    assert driver.note_body(note, body_rule()) == EMAIL_TEXT


# --- the other reads of the peek on a Summit Note window --------------------------


@pytest.mark.parametrize("assignee", ["---", "PO Allocation Pool", "Fake Admin"])
def test_the_original_assignee_is_read_as_it_is_beside_the_unlink_button(
    page, assignee
):
    # A user, a pool or `---` (Joey's live screenshots, 25 Nov 2026).
    assert driver.read_assignee(window(page, summit_note_page(assignee))) == assignee


def test_link_state_and_attachment_read_on_a_summit_note_click_nothing(page, tmp_path):
    note = window(page, summit_note_page())
    guard = ActionGuard()
    log = runlog.RunLog(RUN_ID, guard, directory=tmp_path)

    assert driver.is_unlinked(note, log, NOTE_ID) is True
    assert driver.attachment_names(note) == (FILE,)
    assert driver.note_body(note, body_rule()) == EMAIL_TEXT
    assert guard.history == []

# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""The settled task table (task 4.1; decisions, 3 Nov 2026, M4 gate), offline.

Headless Chromium on a local fake of the project window (page.set_content),
offline: no site is touched. Row 10 and live S6: the window shows before its
task rows render, so an empty read can't be told from "no tasks". The table
is read until two reads in a row are equal and its Compaction Test numbers
equal the `[Compaction Test]` options of the window's "-- Select Task --"
select (one option per task, cancelled ones too), else UnexpectedScreen.
Step 10 (`project_lookup`) and the W1 reopen use the same read. Values are
fake.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys import booking, driver

AGENT = "Agent 1 (MySys Only)"
CLOSE = '<div><span title="Close">close</span></div>'
ROWS = f"""
<tr><td><div><span>(tsk_200001) | Compaction Test</span><button>Undo Cancellation</button></div></td></tr>
<tr><td>{AGENT}</td><td>Perth Scheduling</td><td>Cancelled</td></tr>
<tr><td><div><span>(tsk_200002) | Compaction Test</span><div><button>Cancel</button><button>Hold</button></div></div></td></tr>
<tr><td>{AGENT}</td><td>Perth Scheduling</td><td>New Project</td></tr>
"""
BOTH = ("tsk_200001", "tsk_200002")


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    page = browser.new_page()
    page.set_default_timeout(2000)
    yield page
    page.close()


def project_page(*, options: tuple[str, ...], rows: str, late_ms: int | None) -> str:
    """The project window; its rows arrive `late_ms` after it shows (None:
    never)."""
    choices = "".join(
        f"<option>({task}) [Compaction Test]</option>" for task in options
    )
    later = (
        f"setTimeout(() => {{ document.getElementById('tasks').innerHTML = `{rows}`; }}, {late_ms});"
        if late_ms is not None
        else ""
    )
    return f"""
<div><div>
  <h3>pln_10001 B1 Homes Sample Lane, Sampleville WA 6000</h3>
  <select><option selected>-- Select Task --</option>{choices}</select>
  <ul><li><strong>Client Internal No.:</strong> <span>2600001B</span></li></ul>
  <button>Create New Task</button>
  <table><tbody id="tasks"></tbody></table>
</div>{CLOSE}</div>
<script>{later}</script>"""


def test_rows_that_render_after_the_window_are_waited_for(page):
    page.set_content(project_page(options=BOTH, rows=ROWS, late_ms=600))
    window = booking.project_window(page, "pln_10001")

    tasks = driver.settled_tasks(window)

    assert tasks == {"tsk_200001": "Cancelled", "tsk_200002": "New Project"}


def test_an_empty_table_while_the_select_lists_a_task_is_an_unexpected_screen(
    page, monkeypatch
):
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 1500)
    page.set_content(project_page(options=("tsk_200001",), rows="", late_ms=None))
    window = booking.project_window(page, "pln_10001")

    with pytest.raises(UnexpectedScreen):
        driver.settled_tasks(window)


def test_a_project_with_no_tasks_reads_as_none(page):
    page.set_content(project_page(options=(), rows="", late_ms=None))
    window = booking.project_window(page, "pln_10001")

    assert driver.settled_tasks(window) == {}

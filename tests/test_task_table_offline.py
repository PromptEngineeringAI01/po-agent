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
from playwright.sync_api import Browser, Locator, Page, sync_playwright

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


def test_the_table_is_read_in_one_call_with_the_same_cells(page, monkeypatch):
    # Seam 2, 6 Nov 2026: with 25 tasks (74 rows) a read of one call per row
    # took 8-11 s, so the settled read never got two equal reads in its 15 s
    # and W2 stopped with NO_NEW_TASK. One call reads every row's cells
    # (innerText, cells split on tabs); a row of one empty cell stays [""].
    spacer = "<tr><td></td></tr>"
    page.set_content(project_page(options=BOTH, rows=ROWS + spacer, late_ms=0))
    window = booking.project_window(page, "pln_10001")
    page.wait_for_timeout(100)
    calls = []
    real = Locator.all_inner_texts

    def counted(self):
        calls.append(self)
        return real(self)

    monkeypatch.setattr(Locator, "all_inner_texts", counted)

    rows = driver.task_rows(window)

    assert len(calls) == 1
    assert rows[1] == [AGENT, "Perth Scheduling", "Cancelled"]
    assert rows[3] == [AGENT, "Perth Scheduling", "New Project"]
    assert rows[4] == [""]
    assert rows[0][0].startswith("(tsk_200001) | Compaction Test")
    assert driver.rules.compaction_tasks(rows) == {
        "tsk_200001": "Cancelled",
        "tsk_200002": "New Project",
    }


def test_an_empty_table_counts_as_no_tasks_only_after_the_full_wait(page, monkeypatch):
    # Probe, 4 Nov 2026: the table, its rows and the select's options render
    # together, so two equal empty reads early on prove nothing. Here both
    # arrive 1.5 s after the window shows: they must still be read.
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 3000)
    late = f"""<script>setTimeout(() => {{
      document.getElementById('tasks').innerHTML = `{ROWS}`;
      const select = document.querySelector('select');
      for (const task of {list(BOTH)}) {{
        const option = document.createElement('option');
        option.textContent = '(' + task + ') [Compaction Test]';
        select.appendChild(option);
      }}
    }}, 1500)</script>"""
    page.set_content(project_page(options=(), rows="", late_ms=None) + late)
    window = booking.project_window(page, "pln_10001")

    tasks = driver.settled_tasks(window)

    assert tasks == {"tsk_200001": "Cancelled", "tsk_200002": "New Project"}

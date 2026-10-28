# ruff: noqa: E501 - the fake page HTML and JS read better unwrapped
"""Tests for mysys/driver.py: login and the Note Pool read (task 1.8).

Headless Chromium on a local fake of the test site's login page and Note Pool
panel (page.set_content), offline: no site is touched. The fake behaves as
mapped in docs/screen-map.md rows 01, 26 and 27: the panel has no heading and
holds "New Note" and "Search/filter"; each filter select has a fixed `name`; a
filter change or Refresh reloads the list by itself, replacing the rows and
hiding the footer "Page 1 of 1(N Items)" until it's done. Values are fake.
"""

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from po_agent.core.errors import LoginFailed, UnexpectedScreen
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

POOL = "Agent Pool"
USER = "fake-user"
PASSWORD = "fake-Password-42"

# id, assignee, project, subject/note, locked
ROWS = [
    ("300003", POOL, "---", "[B1 Homes] Order 2600003B/048 file 2600003B_048_1.pdf", 1),
    ("300002", POOL, "---", "Please find attached file 2600002B_048_1.pdf", 1),
    ("300001", POOL, "---", "Please find attached file 2600001B_048_1.pdf", 0),
    ("200001", "<user>", "---", "Please find attached file 2600009B_048_1.pdf", 1),
]

LOGIN_PAGE = """
<title>Test Prompt Engineering - Login</title>
<form onsubmit="return false">
  <input aria-label="Username" name="username">
  <input aria-label="Password" name="password" type="password">
  <button onclick="logIn()">Log in</button>
</form>
<p id="error" hidden>Username and password do not match</p>
<script>
function logIn() {
  const ok = document.querySelector('[name=username]').value === %(user)s
    && document.querySelector('[name=password]').value === %(password)s;
  if (!ok) { document.getElementById('error').hidden = false; return; }
  setTimeout(() => {
    document.body.innerHTML = '<ul><li><span>Project</span></li></ul>';
  }, 200);
}
</script>
"""

FILTERS = {
    "filter_user_id": ["All Users", "Unassigned", "Agent 1 (MySys Only)"],
    "filter_allocation_pool_id": ["All Pools", POOL, "Other Pool"],
    "filter_creator_id": ["All Creators", "<user>"],
    "filter_source": ["All Sources"],
    "filter_status": ["All Status", "Pending", "Solved", "Discard"],
    "filter_lock_status": ["All", "Locked", "Unlocked"],
    "filter_note_type": ["All Note Types", "internal"],
}
DEFAULTS = {
    "filter_user_id": "All Users",
    "filter_allocation_pool_id": "All Pools",
    "filter_creator_id": "All Creators",
    "filter_source": "All Sources",
    "filter_status": "Pending",
    "filter_lock_status": "All",
    "filter_note_type": "All Note Types",
}


def select(name: str, chosen: str) -> str:
    options = "".join(
        f"<option{' selected' if label == chosen else ''}>{label}</option>"
        for label in FILTERS[name]
    )
    return f'<label>{name}<select name="{name}" onchange="reload()">{options}</select></label>'


def note_pool_page(
    *,
    rows=ROWS,
    filters: dict[str, str] | None = None,
    search: str = "",
    duplicates: int = 0,
    pages: int = 1,
    total: int | None = None,
) -> str:
    """The panel after a fresh login (defaults) unless told otherwise.

    duplicates: how many of the next reloads add every row twice while the
    footer keeps the right count (row 27). pages/total: footer override.
    """
    chosen = {**DEFAULTS, **(filters or {})}
    selects = "".join(select(name, chosen[name]) for name in FILTERS)
    config = json.dumps(
        {"rows": rows, "duplicates": duplicates, "pages": pages, "total": total}
    )
    headers = "".join(
        f"<th>{h}</th>"
        for h in [
            "",
            "ID",
            "Assignee",
            "Project",
            "Task",
            "Company",
            "Date",
            "Source",
            "Subject/Note",
            "Status",
            "Note Type",
        ]
    )
    return f"""
<title>Test Prompt Engineering - Note Pool</title>
<div id="user_note__123">
  <div>
    <div><div><button onclick="reload()">Refresh</button><button>Reset Filter</button></div>
      <button>New Note</button></div>
    <div>
      <input placeholder="Search/filter" aria-label="Search/filter" value="{search}">
      <label>Company <input aria-label="Select..."></label><button>close</button>
      {selects}
      <label><input type="checkbox" aria-label="Filter No Company Note">Filter No Company Note</label>
    </div>
  </div>
  <div>
    <table><thead><tr>{headers}</tr></thead><tbody></tbody></table>
    <div id="none" hidden>No record could be found.</div>
    <footer id="footer"><span class="limit"><select><option>20</option><option selected>50</option></select></span>
      <span id="pager"></span></footer>
  </div>
</div>
<script>
const CONFIG = {config};
function value(name) {{
  const s = document.querySelector('select[name=' + name + ']');
  return s.options[s.selectedIndex].text;
}}
function shown() {{
  const pool = value('filter_allocation_pool_id');
  const lock = value('filter_lock_status');
  return CONFIG.rows.filter(r =>
    (pool === 'All Pools' || r[1] === pool) &&
    (lock === 'All' || (lock === 'Locked') === (r[4] === 1)));
}}
function render() {{
  const rows = shown();
  const copies = CONFIG.duplicates > 0 ? 2 : 1;
  CONFIG.duplicates -= 1;
  const body = document.querySelector('tbody');
  body.innerHTML = '';
  for (let c = 0; c < copies; c++) for (const r of rows) {{
    const tr = document.createElement('tr');
    for (const text of ['', r[0], r[1], r[2], '---', '---', '01 Jan 2026 00:00', '<user>', r[3], 'Pending', '']) {{
      const td = document.createElement('td'); td.textContent = text; tr.appendChild(td);
    }}
    body.appendChild(tr);
  }}
  const total = CONFIG.total === null ? rows.length : CONFIG.total;
  document.getElementById('none').hidden = total !== 0;
  document.getElementById('footer').hidden = total === 0;
  document.getElementById('pager').innerHTML =
    'Page 1 of ' + CONFIG.pages + '<br>(' + total + ' Items)';
}}
function reload() {{
  document.getElementById('footer').hidden = true;
  document.querySelector('tbody').innerHTML = '';
  setTimeout(render, 300);
}}
render();
</script>
"""


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser: Browser, monkeypatch) -> Iterator[Page]:
    monkeypatch.setattr(driver, "LOAD_TIMEOUT_MS", 3000)
    page = browser.new_page()
    page.set_default_timeout(3000)
    yield page
    page.close()


@pytest.fixture
def guard() -> ActionGuard:
    return ActionGuard()


def login_page(page: Page) -> None:
    page.set_content(
        LOGIN_PAGE % {"user": json.dumps(USER), "password": json.dumps(PASSWORD)}
    )


def panel_of(page: Page, html: str):
    page.set_content(html)
    panel = driver.note_pool_panel(page)
    driver.wait_for_list(panel)
    return panel


def actions(guard: ActionGuard) -> list[str]:
    return [action for action, _ in guard.history]


# --- login ---------------------------------------------------------------------


def test_login_fills_through_the_guard_and_waits_for_the_project_menu(page, guard):
    login_page(page)

    driver.login(guard, page, USER, PASSWORD)

    assert guard.history == [
        ("login_username", "done"),
        ("login_password", "done"),
        ("login_submit", "done"),
    ]
    assert page.get_by_text("Project", exact=True).is_visible()


def test_a_refused_login_is_login_failed_without_the_password(page, guard):
    login_page(page)

    with pytest.raises(LoginFailed) as caught:
        driver.login(guard, page, USER, "wrong-Password-1")

    assert caught.value.exit_code == 2
    assert "wrong-Password-1" not in str(caught.value)
    assert PASSWORD not in str(caught.value)


# --- the panel and its filters ---------------------------------------------------


def test_the_panel_is_the_one_element_holding_new_note_search_and_the_list(page):
    panel = panel_of(page, note_pool_page())

    assert panel.count() == 1
    assert panel.get_attribute("id") == "user_note__123"


def test_filters_are_set_by_name_and_read_back(page, guard):
    panel = panel_of(page, note_pool_page())

    driver.set_note_pool_filters(guard, panel, POOL)

    assert actions(guard) == ["set_pool_filter", "set_locked_filter"]
    listing = driver.read_note_pool(guard, panel)
    assert [row.note_id for row in listing.rows] == ["300003", "300002"]


def test_a_filter_already_set_is_not_set_again(page, guard):
    panel = panel_of(page, note_pool_page(filters={"filter_lock_status": "Locked"}))

    driver.set_note_pool_filters(guard, panel, POOL)

    assert actions(guard) == ["set_pool_filter"]


@pytest.mark.parametrize(
    "name, value",
    [
        ("filter_status", "All Status"),
        ("filter_user_id", "Unassigned"),
        ("filter_creator_id", "<user>"),
        ("filter_note_type", "internal"),
    ],
)
def test_another_filter_off_its_default_is_an_unexpected_screen(
    page, guard, name, value
):
    panel = panel_of(page, note_pool_page(filters={name: value}))

    with pytest.raises(UnexpectedScreen):
        driver.set_note_pool_filters(guard, panel, POOL)


def test_text_left_in_search_filter_is_an_unexpected_screen(page, guard):
    panel = panel_of(page, note_pool_page(search="300001"))

    with pytest.raises(UnexpectedScreen) as caught:
        driver.set_note_pool_filters(guard, panel, POOL)

    assert "300001" not in str(caught.value)


# --- reading the list ------------------------------------------------------------


def test_rows_are_read_by_column_header(page, guard):
    panel = panel_of(page, note_pool_page())

    listing = driver.read_note_pool(guard, panel)

    assert listing.total == 4
    assert listing.pages == 1
    first = listing.rows[0]
    assert first.note_id == "300003"
    assert first.assignee == POOL
    assert first.project == "---"
    assert first.subject_note == ROWS[0][3]


def test_an_empty_list_reads_as_no_rows(page, guard):
    panel = panel_of(page, note_pool_page(rows=[]))

    listing = driver.read_note_pool(guard, panel)

    assert listing.rows == ()
    assert listing.total == 0


def test_duplicated_rows_get_one_more_refresh(page, guard):
    panel = panel_of(page, note_pool_page(duplicates=1))

    listing = driver.read_note_pool(guard, panel)

    assert actions(guard) == ["refresh_note_pool"]
    assert len(listing.rows) == listing.total == 4


def test_rows_still_not_matching_the_footer_is_an_unexpected_screen(page, guard):
    panel = panel_of(page, note_pool_page(duplicates=5))

    with pytest.raises(UnexpectedScreen):
        driver.read_note_pool(guard, panel)

    assert actions(guard) == ["refresh_note_pool"]


def test_more_pages_reads_page_1_and_says_so(page, guard):
    rows = [(str(300000 + i), POOL, "---", "x", 1) for i in range(50)]
    panel = panel_of(page, note_pool_page(rows=rows, pages=2, total=60))

    listing = driver.read_note_pool(guard, panel)

    assert listing.pages == 2
    assert listing.total == 60
    assert len(listing.rows) == 50


def test_a_list_that_never_loads_is_an_unexpected_screen(page, guard):
    page.set_content(
        "<div><button>New Note</button><input aria-label='Search/filter'><table></table></div>"
    )

    with pytest.raises(UnexpectedScreen):
        driver.wait_for_list(driver.note_pool_panel(page))

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
  const user = value('filter_user_id');
  const pool = value('filter_allocation_pool_id');
  const lock = value('filter_lock_status');
  return CONFIG.rows.filter(r =>
    (user === 'All Users' || r[1] === user) &&
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


def test_the_stale_note_read_lists_only_the_agents_rows_at_the_defaults(page, guard):
    agent = "Agent 1 (MySys Only)"
    rows = [*ROWS, ("300004", agent, "---", "Please find attached file x.pdf", 0)]
    panel = panel_of(page, note_pool_page(rows=rows))

    listing = driver.read_agent_notes(guard, panel, agent)

    assert actions(guard) == []  # All Pools and All are the defaults
    assert [row.note_id for row in listing.rows] == ["300004"]
    assert listing.pages == 1


@pytest.mark.parametrize(
    "name, value",
    [("filter_status", "All Status"), ("filter_user_id", "Unassigned")],
)
def test_the_stale_note_read_off_its_defaults_is_an_unexpected_screen(
    page, guard, name, value
):
    panel = panel_of(page, note_pool_page(filters={name: value}))

    with pytest.raises(UnexpectedScreen):
        driver.read_agent_notes(guard, panel, "Agent 1 (MySys Only)")


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


# --- My Notes: live's stale-Note read (decisions, 10 Nov 2026, My Notes) ---------
# Live's Assigned User filter has no agent option either, and live lists 28
# pages at All Users, so the live profile reads the agent's own My Notes tab
# (Joey's look, 10 Nov 2026): no Assigned User or Assigned Pool filter,
# Status (default Pending), the same New Note, Search/filter, Refresh and
# list as the Note Pool. A Note assigned to the agent by hand shows there.

AGENT = "Agent 1 (MySys Only)"
MY_NOTES_HEADERS = [
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


def my_notes_panel_html(
    *,
    rows=(),
    status: str = "Pending",
    search: str = "",
    pages: int = 1,
    total: int | None = None,
) -> str:
    """A static My Notes panel after a fresh load (rows rendered here)."""
    statuses = "".join(
        f"<option{' selected' if s == status else ''}>{s}</option>"
        for s in ["All Status", "Pending", "Solved", "Discard"]
    )
    headers = "".join(f"<th>{h}</th>" for h in MY_NOTES_HEADERS)
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{text}</td>"
            for text in [
                "",
                r[0],
                r[1],
                "---",
                "---",
                "---",
                "01 Jan 2026 00:00",
                "<user>",
                r[2],
                "Pending",
                "",
            ]
        )
        + "</tr>"
        for r in rows
    )
    count = len(rows) if total is None else total
    listed = (
        f'<footer><span class="limit"><select><option selected>50</option></select></span>'
        f"<span>Page 1 of {pages}<br>({count} Items)</span></footer>"
        if count
        else "<div>No record could be found.</div>"
    )
    return f"""
<div id="my_notes__456">
  <div>
    <div><div><button>Refresh</button><button>Reset Filter</button></div>
      <button>New Note</button><button disabled>Batch Edit (0)</button></div>
    <div>
      <input aria-label="Search/filter" value="{search}">
      <div><span>Company</span><input aria-label="Select..."></div>
      <div><span>Date From</span><input><span>To</span><input></div>
      <div><span>Status</span><select>{statuses}</select></div>
      <div><span>Note Type</span><select><option>All Note Types</option><option>internal</option></select></div>
      <label><input type="checkbox" aria-label="Filter No Company Note">Filter No Company Note</label>
    </div>
  </div>
  <div>
    <table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>
    {listed}
  </div>
</div>
"""


# The Note Pool's panel: the same New Note, Search/filter and list, plus its
# Assigned User and Assigned Pool filters.
POOL_PANEL_HTML = """
<div id="user_note__123">
  <div><button>Refresh</button><button>New Note</button>
    <input aria-label="Search/filter">
    <div><span>Assigned User</span><select name="filter_user_id"><option>All Users</option></select></div>
    <div><span>Assigned Pool</span><select name="filter_allocation_pool_id"><option>All Pools</option></select></div>
    <div><span>Status</span><select name="filter_status"><option selected>Pending</option></select></div>
  </div>
  <div><table><thead><tr><th>ID</th><th>Assignee</th><th>Project</th><th>Subject/Note</th></tr></thead>
    <tbody><tr><td>300001</td><td>Agent Pool</td><td>---</td><td>fake</td></tr></tbody></table>
    <footer><span>Page 1 of 1<br>(1 Items)</span></footer></div>
</div>
"""


def my_notes_of(page: Page, html: str):
    page.set_content(html)
    return driver.my_notes_panel(page)


def test_an_empty_my_notes_lists_no_stale_note(page):
    panel = my_notes_of(page, my_notes_panel_html())

    listing = driver.read_my_notes(panel)

    assert listing.rows == ()
    assert listing.pages == 1


def test_a_note_in_my_notes_is_listed_whatever_its_assignee_cell(page):
    rows = [
        ("300099", AGENT, "Please find attached file x.pdf"),
        ("300098", "<user>", "fake"),
    ]
    panel = my_notes_of(page, my_notes_panel_html(rows=rows))

    listing = driver.read_my_notes(panel)

    assert [row.note_id for row in listing.rows] == ["300099", "300098"]
    assert (listing.total, listing.pages) == (2, 1)


def test_a_second_page_of_my_notes_is_read_as_more_pages(page):
    rows = [("300099", AGENT, "fake"), ("300098", AGENT, "fake")]
    panel = my_notes_of(page, my_notes_panel_html(rows=rows, pages=2, total=60))

    listing = driver.read_my_notes(panel)

    assert listing.pages == 2
    assert [row.note_id for row in listing.rows] == ["300099", "300098"]


def test_my_notes_rows_not_matching_its_footer_is_an_unexpected_screen(page):
    rows = [("300099", AGENT, "fake")]
    panel = my_notes_of(page, my_notes_panel_html(rows=rows, total=2))

    with pytest.raises(UnexpectedScreen):
        driver.read_my_notes(panel)


@pytest.mark.parametrize("status", ["All Status", "Solved"])
def test_my_notes_status_not_pending_is_an_unexpected_screen(page, status):
    panel = my_notes_of(page, my_notes_panel_html(status=status))

    with pytest.raises(UnexpectedScreen):
        driver.read_my_notes(panel)


def test_text_left_in_my_notes_search_is_an_unexpected_screen(page):
    panel = my_notes_of(page, my_notes_panel_html(search="300099"))

    with pytest.raises(UnexpectedScreen) as caught:
        driver.read_my_notes(panel)

    assert "300099" not in str(caught.value)


def test_the_my_notes_panel_is_never_the_note_pool_panel(page):
    panel = my_notes_of(page, f"<div>{POOL_PANEL_HTML}</div>")

    assert panel.count() == 0
    with pytest.raises(UnexpectedScreen):
        driver.read_my_notes(panel)


def test_with_both_panels_in_the_page_my_notes_is_its_own_panel(page):
    html = f"<div>{POOL_PANEL_HTML}{my_notes_panel_html()}</div>"
    panel = my_notes_of(page, html)

    assert panel.count() == 1
    assert panel.get_attribute("id") == "my_notes__456"
    assert driver.read_my_notes(panel).rows == ()


MY_NOTES_MENU_PAGE = """
<style>
  .drop { display: none; }
  li:hover .drop { display: block; }
</style>
<header style="height: 40px">
  <ul><li><span>Project</span><div class="drop">
    <div onclick="document.getElementById('pool').hidden = false">Note Pool</div>
    <div onclick="document.getElementById('mine').hidden = false">My Notes</div>
  </div></li></ul>
</header>
<main style="margin-top: 80px">
  <div id="pool" hidden>%(pool)s</div>
  <div id="mine" hidden>%(mine)s</div>
</main>
"""


def test_open_my_notes_goes_project_then_my_notes_through_the_guard(page, guard):
    page.set_content(
        MY_NOTES_MENU_PAGE % {"pool": POOL_PANEL_HTML, "mine": my_notes_panel_html()}
    )

    panel = driver.open_my_notes(guard, page)

    assert actions(guard)[-2:] == ["open_my_notes", "move_pointer_off_menu"]
    assert set(actions(guard)[:-2]) == {"open_project_tab"}
    assert panel.get_attribute("id") == "my_notes__456"
    assert page.locator("#pool").is_hidden()
    assert driver.read_my_notes(panel).rows == ()

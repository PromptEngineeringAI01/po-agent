"""Login, navigation and reads on MySys; every page action through guard.py.

Built from docs/screen-map.md v1.2 (rows 01, 26, 27) and SPEC.md -> MySys
screen rules. Read-only here except the guarded clicks, fills and selects.
Waits and reads that fail become a fixed `UnexpectedScreen`, never a
Playwright message (it can quote page text).

Found on the test site in 1.8 (25-27 Oct 2026, observed only):
- After login the page needs a moment before the Project menu responds:
  the driver waits for the network to go quiet first.
- The section tab bar's tabs can't be clicked by Playwright (the page body
  takes the click), so the driver opens the Note Pool from the Project
  menu's own list: a first Project click loads the module, a second one
  opens the list.
- A filter change or Refresh replaces the list's rows and hides the footer
  until the reload is done. The footer's text is "Page 1 of 1(N Items)";
  its inner text has a line break before "(".
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from playwright.sync_api import ElementHandle, Locator, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError
from pydantic import ValidationError

from po_agent.b1.models import NotePoolRow
from po_agent.core.errors import LoginFailed, UnexpectedScreen
from po_agent.mysys.guard import ActionGuard

LOAD_TIMEOUT_MS = 15_000
MENU_TRIES = 3
FOOTER = re.compile(r"^Page (\d+) of (\d+)\s*\((\d+) Items?\)$")
NO_RECORD = "No record could be found."
LOCKED = "Locked"
POOL_FILTER = "filter_allocation_pool_id"
LOCK_FILTER = "filter_lock_status"
# Every Note Pool filter and its default after a fresh login (rows 01, 27).
FILTER_DEFAULTS = {
    "filter_user_id": "All Users",
    POOL_FILTER: "All Pools",
    "filter_creator_id": "All Creators",
    "filter_source": "All Sources",
    "filter_status": "Pending",
    LOCK_FILTER: "All",
    "filter_note_type": "All Note Types",
}
COLUMNS = {
    "note_id": "ID",
    "assignee": "Assignee",
    "project": "Project",
    "subject_note": "Subject/Note",
}


@dataclass(frozen=True)
class NotePoolList:
    """Page 1 of the Note Pool as read; `total` and `pages` from its footer."""

    rows: tuple[NotePoolRow, ...]
    total: int
    pages: int


@contextmanager
def open_browser(*, headed: bool, slow_mo: int) -> Iterator[Page]:
    """A fresh Chromium context; no storage state is loaded or saved."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed, slow_mo=slow_mo)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(LOAD_TIMEOUT_MS)
            yield page
        finally:
            browser.close()


def go_home(page: Page, base_url: str) -> None:
    """Load base_url (a navigation, not a click)."""
    try:
        page.goto(base_url)
    except PlaywrightError:
        raise UnexpectedScreen("base_url did not load") from None


def login(guard: ActionGuard, page: Page, username: str, password: str) -> None:
    """Log in on the login page; LoginFailed if the app doesn't appear."""
    body = page.locator("body")
    guard.act(
        "login_username",
        body,
        page.get_by_role("textbox", name="Username", exact=True),
        username,
    )
    guard.act(
        "login_password",
        body,
        page.get_by_role("textbox", name="Password", exact=True),
        password,
    )
    guard.act(
        "login_submit", body, page.get_by_role("button", name="Log in", exact=True)
    )
    try:
        _project_title(page).wait_for(state="visible", timeout=LOAD_TIMEOUT_MS)
    except PlaywrightError:
        raise LoginFailed("login did not reach the app") from None
    _network_idle(page)


def open_note_pool(guard: ActionGuard, page: Page) -> Locator:
    """Project menu -> Note Pool; returns the panel once its list is shown."""
    menu = _project_menu(page)
    title = _project_title(page)
    item = menu.get_by_text("Note Pool", exact=True)
    for _ in range(MENU_TRIES):
        guard.act("open_project_tab", menu, title)
        _network_idle(page)
        try:
            item.wait_for(state="visible", timeout=2000)
            break
        except PlaywrightError:
            continue
    else:
        raise UnexpectedScreen("Note Pool menu item did not show")
    guard.act("open_note_pool", menu, item)
    panel = note_pool_panel(page)
    wait_for_list(panel)
    return panel


def note_pool_panel(page: Page) -> Locator:
    """The innermost element holding New Note, Search/filter and the list.

    Row 26: the panel has no heading and a generated id. Every ancestor holds
    the same controls, so the panel is the candidate with no candidate inside.
    """
    listed = page.locator("table").or_(page.get_by_text(NO_RECORD, exact=True))
    candidates = (
        page.locator("*")
        .filter(has=page.get_by_role("button", name="New Note", exact=True))
        .filter(has=page.get_by_role("textbox", name="Search/filter", exact=True))
        .filter(has=listed)
    )
    return candidates.filter(has_not=candidates)


def wait_for_list(panel: Locator, before: ElementHandle | None = None) -> None:
    """Wait for a (re)loaded list: `before`, a row from the old list, goes
    away, then the footer or "No record could be found." shows."""
    try:
        if before is not None:
            before.wait_for_element_state("hidden", timeout=LOAD_TIMEOUT_MS)
        _footer(panel).or_(_no_record(panel)).wait_for(
            state="visible", timeout=LOAD_TIMEOUT_MS
        )
    except PlaywrightError:
        raise UnexpectedScreen("Note Pool list did not load") from None


def set_note_pool_filters(guard: ActionGuard, panel: Locator, pool_name: str) -> None:
    """Assigned Pool = pool_name, Locked/Unlocked = Locked, each read back;
    every other filter at its default and every textbox empty."""
    wanted = {**FILTER_DEFAULTS, POOL_FILTER: pool_name, LOCK_FILTER: LOCKED}
    _set_filter(guard, panel, "set_pool_filter", POOL_FILTER, pool_name)
    _set_filter(guard, panel, "set_locked_filter", LOCK_FILTER, LOCKED)
    try:
        for name, label in wanted.items():
            if _chosen(panel, name) != label:
                raise UnexpectedScreen("Note Pool filter not as expected", field=name)
        if any(box.input_value() for box in panel.get_by_role("textbox").all()):
            raise UnexpectedScreen("Note Pool text filter not empty")
        no_company = panel.get_by_role(
            "checkbox", name="Filter No Company Note", exact=True
        )
        if no_company.is_checked():
            raise UnexpectedScreen("Note Pool filter not as expected")
    except PlaywrightError:
        raise UnexpectedScreen("Note Pool filters not readable") from None


def read_note_pool(guard: ActionGuard, panel: Locator) -> NotePoolList:
    """Page 1 of the list. Its row count must equal the footer's (or the page
    size, with more pages); else one more Refresh, then UnexpectedScreen."""
    try:
        listing = _read_list(panel)
        if listing is None:
            before = _first_row(panel)
            refresh = panel.get_by_role("button", name="Refresh", exact=True)
            guard.act("refresh_note_pool", panel, refresh)
            wait_for_list(panel, before)
            listing = _read_list(panel)
    except PlaywrightError:
        raise UnexpectedScreen("Note Pool list not readable") from None
    if listing is None:
        raise UnexpectedScreen("Note Pool rows do not match the footer")
    return listing


def _project_menu(page: Page) -> Locator:
    # The top menu's Project item; its own list holds Note Pool (row 26).
    return (
        page.locator("li")
        .filter(has=page.get_by_text("Project", exact=True))
        .filter(has=page.get_by_text("Note Pool", exact=True))
    )


def _project_title(page: Page) -> Locator:
    return page.locator("li").get_by_text("Project", exact=True)


def _network_idle(page: Page) -> None:
    # https://playwright.dev/python/docs/api/class-page#page-wait-for-load-state
    try:
        page.wait_for_load_state("networkidle", timeout=LOAD_TIMEOUT_MS)
    except PlaywrightError:
        raise UnexpectedScreen("page did not settle") from None


def _footer(panel: Locator) -> Locator:
    return panel.get_by_text(FOOTER).visible


def _no_record(panel: Locator) -> Locator:
    return panel.get_by_text(NO_RECORD, exact=True).visible


def _first_row(panel: Locator) -> ElementHandle | None:
    rows = panel.locator("tbody tr")
    return rows.first.element_handle() if rows.count() else None


def _chosen(panel: Locator, name: str) -> str:
    select = panel.locator(f'select[name="{name}"]')
    return (select.locator("option:checked").text_content() or "").strip()


def _set_filter(
    guard: ActionGuard, panel: Locator, action: str, name: str, label: str
) -> None:
    try:
        if _chosen(panel, name) == label:
            return  # already set: choosing it again wouldn't reload the list
        before = _first_row(panel)
    except PlaywrightError:
        raise UnexpectedScreen("Note Pool filters not readable") from None
    guard.act(action, panel, panel.locator(f'select[name="{name}"]'), label)
    wait_for_list(panel, before)


def _read_list(panel: Locator) -> NotePoolList | None:
    """The list, or None if its row count doesn't match the footer."""
    rows = panel.locator("tbody tr")
    if _no_record(panel).count():
        return NotePoolList(rows=(), total=0, pages=1) if rows.count() == 0 else None
    match = FOOTER.match((_footer(panel).text_content() or "").strip())
    if match is None:
        raise UnexpectedScreen("Note Pool footer not recognised")
    pages, total = int(match.group(2)), int(match.group(3))
    expected = total if pages == 1 else _page_size(panel)
    if rows.count() != expected:
        return None
    headers = [h.strip() for h in panel.locator("thead th").all_text_contents()]
    try:
        index = {field: headers.index(name) for field, name in COLUMNS.items()}
    except ValueError:
        raise UnexpectedScreen("Note Pool columns not recognised") from None
    read = []
    for row in rows.all():
        cells = [c.strip() for c in row.locator("td").all_inner_texts()]
        if len(cells) != len(headers):
            raise UnexpectedScreen("Note Pool row not recognised")
        try:
            read.append(NotePoolRow(**{f: cells[i] for f, i in index.items()}))
        except ValidationError:
            # from None: pydantic's message quotes the cell.
            raise UnexpectedScreen("Note Pool row not recognised") from None
    return NotePoolList(rows=tuple(read), total=total, pages=pages)


def _page_size(panel: Locator) -> int:
    # Row 26: the page size is the select in the footer (`.limit > select`).
    size = panel.locator(".limit > select option:checked").text_content() or ""
    if not size.strip().isdigit():
        raise UnexpectedScreen("Note Pool page size not recognised")
    return int(size.strip())

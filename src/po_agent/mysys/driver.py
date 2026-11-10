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
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import (
    Download,
    ElementHandle,
    Locator,
    Page,
    sync_playwright,
)
from playwright.sync_api import Error as PlaywrightError
from pydantic import ValidationError

from po_agent.b1 import reader_rules as rules
from po_agent.b1.decision import Site, check_project, match_project
from po_agent.b1.models import (
    CompactionTask,
    MySysLookup,
    NotePoolRow,
    Proceed,
    SearchRow,
    Skip,
)
from po_agent.core.errors import (
    LoginFailed,
    PartialWrite,
    UnexpectedScreen,
    WriteNotStarted,
)
from po_agent.core.runlog import RunLog
from po_agent.mysys.guard import ActionGuard

LOAD_TIMEOUT_MS = 15_000
MENU_TRIES = 3
FOOTER = re.compile(r"^Page (\d+) of (\d+)\s*\((\d+) Items?\)$")
NO_RECORD = "No record could be found."
PROJECTS_NO_RECORD = "No record found."
POLL_MS = 500
EMPTY_SETTLE_MS = 3000  # My Notes: how long an empty list must stay empty
OPEN_TRIES = 4  # x 15 s
SELECT_USER = "--Select User--"
SELECT_POOL = "--Select Pool--"
ALL_POOLS = "All Pools"
ALL_LOCKED = "All"
# Row 13: a linked Note shows a button named for its project.
PROJECT_BUTTON = re.compile(r"^pln_\d+$")
LOCKED = "Locked"
POOL_FILTER = "filter_allocation_pool_id"
LOCK_FILTER = "filter_lock_status"
USER_FILTER = "filter_user_id"
ALL_USERS = "All Users"
PENDING = "Pending"
MY_NOTES = "My Notes"  # the Project menu item (decisions, 10 Nov 2026, My Notes)
# Every Note Pool filter and its default after a fresh login (rows 01, 27).
FILTER_DEFAULTS = {
    USER_FILTER: ALL_USERS,
    POOL_FILTER: "All Pools",
    "filter_creator_id": "All Creators",
    "filter_source": "All Sources",
    "filter_status": PENDING,
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
def open_browser(
    *, headed: bool, slow_mo: int, downloads: Path | None = None
) -> Iterator[Page]:
    """A fresh Chromium context; no storage state is loaded or saved.
    Downloads go to `downloads`, the run's po-agent-dl-<run_id> folder (D2)."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not headed, slow_mo=slow_mo, downloads_path=downloads
        )
        try:
            context = browser.new_context(accept_downloads=downloads is not None)
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
    _set_filter(guard, panel, "set_pool_filter", POOL_FILTER, pool_name)
    _set_filter(guard, panel, "set_locked_filter", LOCK_FILTER, LOCKED)
    _check_filters(
        panel, {**FILTER_DEFAULTS, POOL_FILTER: pool_name, LOCK_FILTER: LOCKED}
    )


def read_agent_notes(guard: ActionGuard, panel: Locator, agent: str) -> NotePoolList:
    """The test profile's stale-Note read (D6): Assigned Pool = All Pools and
    Locked/Unlocked = All, each read back; Assigned User at All Users (the
    test site's Assigned User list has no agent; decisions, 3 Nov 2026),
    Status left at Pending, every other filter at its default and
    Search/filter empty. Page 1's rows with `agent` as Assignee; `total` and
    `pages` as the footer says. Live reads My Notes instead (read_my_notes)."""
    _set_filter(guard, panel, "set_pool_filter", POOL_FILTER, ALL_POOLS)
    _set_filter(guard, panel, "set_locked_filter", LOCK_FILTER, ALL_LOCKED)
    _check_filters(panel, FILTER_DEFAULTS)
    listing = read_note_pool(guard, panel)
    rows = tuple(row for row in listing.rows if row.assignee == agent)
    return NotePoolList(rows=rows, total=listing.total, pages=listing.pages)


# Live's stale-Note read: My Notes (decisions, 10 Nov 2026, My Notes)


def open_my_notes(guard: ActionGuard, page: Page) -> Locator:
    """Project menu -> My Notes, as open_note_pool does Note Pool; then the
    pointer off the menu and the list loaded. Read only: nothing in MySys
    changes. Returns the My Notes panel."""
    menu = _project_menu(page)
    title = _project_title(page)
    item = menu.get_by_text(MY_NOTES, exact=True)
    for _ in range(MENU_TRIES):
        guard.act("open_project_tab", menu, title)
        _network_idle(page)
        if _shows(item, 2000):
            break
    else:
        raise UnexpectedScreen("My Notes menu item did not show")
    guard.act("open_my_notes", menu, item)
    leave_menu(guard, page)
    panel = my_notes_panel(page)
    wait_for_list(panel)
    return panel


def my_notes_panel(page: Page) -> Locator:
    """The My Notes panel: the innermost visible element holding New Note,
    Search/filter and the list, and no Assigned User or Assigned Pool
    filter. The Note Pool panel holds the same New Note, Search/filter and
    list plus those two filters, so neither it nor any element holding both
    panels matches. Never a generated id or nth (row 26)."""
    listed = page.locator("table").or_(page.get_by_text(NO_RECORD, exact=True))
    pool_filters = (
        page.locator(f'select[name="{POOL_FILTER}"]')
        .or_(page.locator(f'select[name="{USER_FILTER}"]'))
        .or_(page.get_by_text("Assigned Pool", exact=True))
        .or_(page.get_by_text("Assigned User", exact=True))
    )
    candidates = (
        page.locator("*")
        .filter(has=page.get_by_role("button", name="New Note", exact=True))
        .filter(has=page.get_by_role("textbox", name="Search/filter", exact=True))
        .filter(has=listed)
        .filter(has_not=pool_filters)
    )
    return candidates.filter(has_not=candidates).visible


def read_my_notes(panel: Locator) -> NotePoolList:
    """Page 1 of My Notes, once its filters read back: Status = Pending,
    every textbox (Search/filter too) empty, Filter No Company Note unticked
    where shown. My Notes lists the Notes assigned to the logged-in agent
    (Joey, live, 10 Nov 2026), so every row is listed, whatever its
    Assignee cell. The one empty list is "No record could be found." with
    no rows, read twice EMPTY_SETTLE_MS apart; rows that don't match the
    footer are an UnexpectedScreen (no Refresh: nothing on My Notes is
    clicked). Reads only."""
    try:
        if panel.count() != 1:
            raise UnexpectedScreen("My Notes panel not found once")
        _check_my_notes_filters(panel)
        listing = _read_my_notes_list(panel)
        if not listing.rows:
            # An empty list counts only if it is still empty a moment later:
            # "No record could be found." can show while the rows load, and
            # networkidle doesn't wait for a list loaded after the page.
            panel.page.wait_for_timeout(EMPTY_SETTLE_MS)
            listing = _read_my_notes_list(panel)
        return listing
    except PlaywrightError:
        raise UnexpectedScreen("My Notes list not readable") from None


def _check_my_notes_filters(panel: Locator) -> None:
    page = panel.page
    # The Status filter's block: the innermost element holding the exact
    # text "Status" and a select, outside the list (whose header also reads
    # "Status").
    blocks = (
        page.locator("*")
        .filter(has=page.get_by_text("Status", exact=True))
        .filter(has=page.locator("select"))
        .filter(has_not=page.locator("table"))
    )
    status = panel.locator("*").and_(blocks.filter(has_not=blocks)).locator("select")
    if status.count() != 1:
        raise UnexpectedScreen("My Notes Status filter not found once")
    chosen = (status.locator("option:checked").text_content() or "").strip()
    if chosen != PENDING:
        raise UnexpectedScreen("My Notes filter not as expected", field="Status")
    if any(box.input_value() for box in panel.get_by_role("textbox").all()):
        raise UnexpectedScreen("My Notes text filter not empty")
    no_company = panel.get_by_role(
        "checkbox", name="Filter No Company Note", exact=True
    )
    if no_company.count() and no_company.is_checked():
        raise UnexpectedScreen("My Notes filter not as expected")


def _read_my_notes_list(panel: Locator) -> NotePoolList:
    rows = panel.locator("tbody tr")
    if _no_record(panel).count():
        if rows.count():
            raise UnexpectedScreen("My Notes rows do not match the footer")
        return NotePoolList(rows=(), total=0, pages=1)
    match = FOOTER.match((_footer(panel).text_content() or "").strip())
    if match is None:
        raise UnexpectedScreen("My Notes footer not recognised")
    pages, total = int(match.group(2)), int(match.group(3))
    count = rows.count()
    if count == 0 or (pages == 1 and count != total):
        raise UnexpectedScreen("My Notes rows do not match the footer")
    headers = [h.strip() for h in panel.locator("thead th").all_text_contents()]
    try:
        index = {field: headers.index(name) for field, name in COLUMNS.items()}
    except ValueError:
        raise UnexpectedScreen("My Notes columns not recognised") from None
    read = []
    for row in rows.all():
        cells = [c.strip() for c in row.locator("td").all_inner_texts()]
        if len(cells) != len(headers):
            raise UnexpectedScreen("My Notes row not recognised")
        try:
            read.append(NotePoolRow(**{f: cells[i] for f, i in index.items()}))
        except ValidationError:
            # from None: pydantic's message quotes the cell.
            raise UnexpectedScreen("My Notes row not recognised") from None
    return NotePoolList(rows=tuple(read), total=total, pages=pages)


def _check_filters(panel: Locator, wanted: dict[str, str]) -> None:
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


# Windows and labels (row 26), shared with booking.py


def _innermost(page: Page, *holds: Locator) -> Locator:
    """The innermost visible element that holds every locator in `holds`."""
    found = page.locator("*")
    for inner in holds:
        found = found.filter(has=inner)
    return found.filter(has_not=found).visible


def _exact(text: str) -> re.Pattern[str]:
    return re.compile(rf"^{re.escape(text)}$")


def _label_pattern(label: str) -> re.Pattern[str]:
    """The label's words with any whitespace between them: live S5 (28 Oct
    2026) failed on "Client Internal No.:" whose spaces aren't plain spaces
    in the page (ARIA snapshots show them as plain). JavaScript's \\s, which
    Playwright uses for the match, includes the non-breaking space."""
    words = (re.escape(word) for word in label.split())
    return re.compile(r"^\s*" + r"\s+".join(words) + r"\s*$")


def _labelled(window: Locator, label: str) -> str:
    """The text after a bold label: "Assignee: Agent Pool" -> "Agent Pool".
    The label's parent also holds an Unlink button on the Note window.

    Waits up to 15 s for exactly one visible label: live (28 Oct 2026) the
    project window's details render after the window shows, and Assign
    re-renders the Note window. Two visible labels fail at once (strict)."""
    strong = window.locator("strong").filter(has_text=_label_pattern(label)).visible
    try:
        strong.wait_for(state="visible", timeout=LOAD_TIMEOUT_MS)
    except PlaywrightError:
        raise UnexpectedScreen("label not found once") from None
    try:
        text = strong.locator("xpath=..").inner_text()
    except PlaywrightError:
        raise UnexpectedScreen("label not readable") from None
    # str.split() splits on any Unicode whitespace, the non-breaking space too.
    value = " ".join(text.split()).removeprefix(" ".join(label.split())).strip()
    return value.removesuffix("Unlink").strip()


def label_block(window: Locator, label: str, control: str) -> Locator:
    """The innermost element in `window` holding the exact label text and a
    `control` (CSS), e.g. the "PO Number" block and its input (rows 08-09:
    every Create New Task field sits in its own label block). Built from the
    page root: a has_not locator is evaluated inside each candidate."""
    page = window.page
    found = (
        page.locator("*")
        .filter(has=page.get_by_text(label, exact=True))
        .filter(has=page.locator(control))
    )
    return window.locator("*").and_(found.filter(has_not=found))


def field_by_label(window: Locator, label: str, control: str) -> Locator:
    """The `control` in its label block: never `nth` or a generated id."""
    return label_block(window, label, control).locator(control)


def _shows(locator: Locator, timeout: int | None = None) -> bool:
    """Waits (the page's default timeout, else `timeout`) for one element."""
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except PlaywrightError:
        return False


def _polls(window: Locator, read: Callable[[], bool]) -> bool:
    """Polls `read` until it is true, for up to 15 s; a read that fails for a
    moment (the window re-rendering) is tried again."""
    deadline = time.monotonic() + LOAD_TIMEOUT_MS / 1000
    while True:
        try:
            if read():
                return True
        except (UnexpectedScreen, PlaywrightError):
            pass
        if time.monotonic() >= deadline:
            return False
        window.page.wait_for_timeout(POLL_MS)


# Moving between windows (rows 25, 27)


def leave_menu(guard: ActionGuard, page: Page) -> None:
    """Moves the pointer off the header after a Project menu choice.

    Root cause of "page blocked" (27-28 Oct 2026): Playwright's pointer stays
    where its last click left it, in the header; while the header is hovered
    the page covers the body and takes no click below it ("<body> intercepts
    pointer events"). A click elsewhere in the header keeps it there. So the
    guard moves the pointer, with no click, onto the list's status line below
    the header (move_pointer_off_menu; decisions, 28 Oct 2026)."""
    status = (
        page.get_by_text(FOOTER)
        .or_(page.get_by_text(NO_RECORD, exact=True))
        .or_(page.get_by_text(PROJECTS_NO_RECORD, exact=True))
        .visible
    )
    if not _shows(status, LOAD_TIMEOUT_MS):
        raise UnexpectedScreen("list status line not shown")
    guard.act("move_pointer_off_menu", page.locator("body"), status)
    item = _project_menu(page).get_by_text("Note Pool", exact=True)
    try:
        item.wait_for(state="hidden", timeout=LOAD_TIMEOUT_MS)
    except PlaywrightError:
        raise UnexpectedScreen("Project menu did not close") from None


def reload_home(
    guard: ActionGuard, page: Page, base_url: str, username: str, password: str
) -> None:
    """Reloads base_url between Notes (every window closes, nothing in MySys
    changes) and logs in again if the login page shows. After a reload the
    tab bar is hidden until Project is clicked, which open_note_pool does
    (row 27). Never Minimize or a taskbar entry."""
    go_home(page, base_url)
    login_box = page.get_by_role("textbox", name="Username", exact=True)
    if not _shows(_project_title(page).or_(login_box).first, LOAD_TIMEOUT_MS):
        raise UnexpectedScreen("base_url showed neither the app nor the login")
    try:
        logged_out = login_box.count() > 0
    except PlaywrightError:
        raise UnexpectedScreen("base_url not readable") from None
    if logged_out:
        login(guard, page, username, password)
    else:
        _network_idle(page)


def _open_retried(
    guard: ActionGuard, action: str, scope: Locator, target: Locator
) -> None:
    """An opening or refreshing click (it changes nothing in MySys), tried
    OPEN_TRIES times in case the page is still covered (see leave_menu).
    Playwright never clicks while the target is covered, so a retry cannot
    act twice. A guard refusal is never retried."""
    for attempt in range(OPEN_TRIES):
        try:
            guard.act(action, scope, target)
            return
        except UnexpectedScreen:
            if attempt == OPEN_TRIES - 1:
                raise


def search_note(
    guard: ActionGuard,
    page: Page,
    base_url: str,
    username: str,
    password: str,
    note_id: str,
) -> tuple[Locator, NotePoolList]:
    """Cross-cutting rule "Finding a Note again", up to the read: reload, the
    Note Pool under All Pools and All, search the Note ID (fill, then
    Refresh: row 27), page 1 read. Every row whose ID contains the Note ID
    is listed: pick the one with exact_row."""
    reload_home(guard, page, base_url, username, password)
    panel = open_note_pool(guard, page)
    leave_menu(guard, page)
    _set_filter(guard, panel, "set_pool_filter", POOL_FILTER, ALL_POOLS)
    _set_filter(guard, panel, "set_locked_filter", LOCK_FILTER, ALL_LOCKED)
    search = panel.get_by_role("textbox", name="Search/filter", exact=True)
    guard.act("search_note_pool", panel, search, note_id)
    try:
        before = _first_row(panel)
    except PlaywrightError:
        raise UnexpectedScreen("Note Pool list not readable") from None
    refresh = panel.get_by_role("button", name="Refresh", exact=True)
    _open_retried(guard, "refresh_note_pool", panel, refresh)
    wait_for_list(panel, before)
    return panel, read_note_pool(guard, panel)


def find_note_again(
    guard: ActionGuard,
    page: Page,
    base_url: str,
    username: str,
    password: str,
    note_id: str,
) -> Locator:
    """search_note, then the one row whose ID cell equals the Note ID,
    opened. The reopened window has Send Email ticked again."""
    panel, listing = search_note(guard, page, base_url, username, password, note_id)
    if not found_once(listing, note_id):
        raise UnexpectedScreen("Note not found again", note_id=note_id)
    return open_note(guard, page, panel, note_id)


def gone_from_pending(
    guard: ActionGuard,
    page: Page,
    base_url: str,
    username: str,
    password: str,
    note_id: str,
) -> None:
    """W5's last read-back (row 14): search_note, the Status filter read
    back at Pending (never chosen: it lists Discard), and no row whose ID
    cell equals the Note ID. Not find_note_again, which needs the Note."""
    panel, listing = search_note(guard, page, base_url, username, password, note_id)
    try:
        status = _chosen(panel, "filter_status")
    except PlaywrightError:
        raise UnexpectedScreen("Note Pool filters not readable") from None
    if status != FILTER_DEFAULTS["filter_status"]:
        raise UnexpectedScreen("Note Pool not filtered on Pending", note_id=note_id)
    # Only page 1 is read: a second page could still hold the Note.
    if listing.pages != 1 or any(row.note_id == note_id for row in listing.rows):
        raise UnexpectedScreen("Note still Pending after Solved", note_id=note_id)


def exact_row(listing: NotePoolList, note_id: str) -> NotePoolRow | None:
    """The one row whose ID cell equals the Note ID, else None (none, or the
    same ID twice): the search matches substrings, so 300001 also lists
    3000012."""
    rows = [row for row in listing.rows if row.note_id == note_id]
    return rows[0] if len(rows) == 1 else None


def found_once(listing: NotePoolList, note_id: str) -> bool:
    return exact_row(listing, note_id) is not None


# Note window (rows 02-04, 13, 15b)


def note_window(page: Page, note_id: str) -> Locator:
    heading = page.get_by_role(
        "heading", name=re.compile(rf"^Note {re.escape(note_id)} - ")
    )
    return _innermost(page, heading, page.get_by_role("group", name="Status buttons"))


def open_note(guard: ActionGuard, page: Page, panel: Locator, note_id: str) -> Locator:
    """Opens the Note from its Note Pool row by the row's ID cell."""
    cell = panel.get_by_role("cell", name=note_id, exact=True)
    _open_retried(guard, "open_note", panel, cell)
    window = note_window(page, note_id)
    if not _shows(window, LOAD_TIMEOUT_MS):
        raise UnexpectedScreen("Note window did not open", note_id=note_id)
    return window


def read_assignee(window: Locator) -> str:
    return _labelled(window, "Assignee:")


def read_status(window: Locator) -> str:
    return _labelled(window, "Status:")


def _log_lines(window: Locator) -> Locator:
    # Row 02: the list beside the h4 "Logs", one item per line, newest first.
    page = window.page
    logs = page.locator("*").filter(
        has=page.get_by_role("heading", name="Logs", exact=True)
    )
    holder = logs.filter(has=page.get_by_role("list")).filter(
        has_not=logs.filter(has=page.get_by_role("list"))
    )
    return window.locator("*").and_(holder).get_by_role("list").get_by_role("listitem")


def log_line_count(window: Locator) -> int:
    try:
        return _log_lines(window).count()
    except PlaywrightError:
        raise UnexpectedScreen("Note log not readable") from None


def _new_log_line(window: Locator, before: int, was: str, now: str) -> bool:
    """One more log line than `before`: the newest is "User Assigned" from
    `was` (when known) to `now`."""
    lines = _log_lines(window)
    if lines.count() != before + 1:
        return False
    newest = lines.first
    said = " ".join(newest.locator("em").inner_text().split())
    names = [" ".join(s.split()) for s in newest.locator("strong").all_inner_texts()]
    return (
        "User Assigned:" in said
        and len(names) == 2
        and names[1] == now
        and (not was or names[0] == was)
    )


def is_unlinked(window: Locator, log: RunLog, note_id: str) -> bool:
    """Step 2a: True if Link to Project shows (go on); False if a project
    button or Change Project shows (NOTE_ALREADY_LINKED). Anything else stops.
    Presses nothing: never Change Project (Must never #2)."""
    try:
        link = window.get_by_role("button", name="Link to Project", exact=True)
        change = window.get_by_role("button", name="Change Project", exact=True)
        project = window.get_by_role("button", name=PROJECT_BUTTON)
        links, linked = link.count(), change.count() + project.count()
    except PlaywrightError:
        raise UnexpectedScreen("Note window not readable", note_id=note_id) from None
    known = (links, linked) == (1, 0) or (links == 0 and linked > 0)
    log.event(
        "read_back", note_id=note_id, step="2a", ok=known, field="link_to_project"
    )
    if not known:
        raise UnexpectedScreen("link state not recognised", note_id=note_id, step="2a")
    return links == 1


def _email_box(window: Locator) -> Locator:
    return window.get_by_role("checkbox", name="Send Email Notification", exact=True)


def _email_ticked(window: Locator) -> bool:
    try:
        return _email_box(window).is_checked()
    except PlaywrightError:
        raise UnexpectedScreen("Send Email Notification not readable") from None


def _list(window: Locator, placeholder: str) -> Locator:
    # Row 26: the Note window's select that holds the placeholder option.
    option = window.page.locator("option").filter(has_text=_exact(placeholder))
    return window.locator("select").filter(has=option)


def _chosen_in(select: Locator) -> str:
    try:
        return (select.locator("option:checked").text_content() or "").strip()
    except PlaywrightError:
        raise UnexpectedScreen("Note window list not readable") from None


def _read_back(
    window: Locator,
    log: RunLog,
    note_id: str,
    step: str,
    field: str,
    read: Callable[[], bool],
) -> None:
    ok = _polls(window, read)
    log.event("read_back", note_id=note_id, step=step, ok=ok, field=field)
    if not ok:
        raise UnexpectedScreen(
            "read-back failed", note_id=note_id, step=step, field=field
        )


def _assign(
    guard: ActionGuard,
    window: Locator,
    log: RunLog,
    note_id: str,
    step: str,
    was: str,
    now: str,
) -> None:
    """Send Email read back unticked right before the one Assign (Must never
    #4), then "Assignee:" and the new log line read back."""
    unticked = not _email_ticked(window)
    log.event("email_notification_unticked", note_id=note_id, step=step, ok=unticked)
    if not unticked:
        raise UnexpectedScreen(
            "Send Email Notification still ticked", note_id=note_id, step=step
        )
    before = log_line_count(window)
    assign = window.get_by_role("button", name="Assign", exact=True)
    guard.act("assign_note", window, assign)
    _read_back(
        window, log, note_id, step, "assignee", lambda: read_assignee(window) == now
    )
    _read_back(
        window,
        log,
        note_id,
        step,
        "log_line",
        lambda: _new_log_line(window, before, was, now),
    )


def _untick(guard: ActionGuard, window: Locator) -> None:
    # Ticked whenever a Note window opens (row 02).
    if _email_ticked(window):
        guard.act("untick_send_email_notification", window, _email_box(window))


def take_note(
    guard: ActionGuard, window: Locator, agent: str, log: RunLog, note_id: str
) -> None:
    """Step 2: Send Email unticked, user list = the agent, pool list left at
    --Select Pool--, one Assign; read back the assignee and the new log line
    "User Assigned: ... to <agent>"."""
    step = "2"
    _untick(guard, window)
    guard.act("select_note_user", window, _list(window, SELECT_USER), agent)
    if _chosen_in(_list(window, SELECT_POOL)) != SELECT_POOL:
        raise UnexpectedScreen("pool list not at its placeholder", note_id=note_id)
    _assign(guard, window, log, note_id, step, was="", now=agent)
    log.flush(note_id=note_id, step=step)


def return_note(
    guard: ActionGuard,
    window: Locator,
    agent: str,
    pool: str,
    log: RunLog,
    note_id: str,
) -> None:
    """Row 15b: Send Email unticked, --Select User-- and the pool, one Assign,
    no key press; read back Assignee = pool, the new log line "From <agent>
    to <pool>" and Status Pending. The lists reset and Assign is disabled
    afterwards, as expected."""
    step = "return"
    _untick(guard, window)
    guard.act("select_note_user", window, _list(window, SELECT_USER), SELECT_USER)
    guard.act("select_note_pool", window, _list(window, SELECT_POOL), pool)
    _assign(guard, window, log, note_id, step, was=agent, now=pool)
    _read_back(
        window,
        log,
        note_id,
        step,
        "status",
        lambda: read_status(window).startswith("Pending"),
    )
    log.flush(note_id=note_id, step=step)


# Attachment and download (rows 02, 05)


def note_body(window: Locator, file_name: str) -> str:
    """The Note's body (row 02): the one source in the window whose text ends
    with the file name, either a <pre> (test site, 27 Oct 2026; the title
    heading and the file-name <span> end with it too) or the document body
    of an iframe (live email Notes: MySys's get_email_body; decisions, 10
    Nov 2026, Note body iframe). None or more than one -> UnexpectedScreen.

    An iframe's document loads after the window shows, so while any iframe
    in the window is still empty the read waits, up to 15 s. Read only:
    nothing in a frame is clicked. Untrusted data: never printed."""
    ends = re.compile(rf"{re.escape(file_name)}\s*$")
    pres = window.locator("pre").filter(has_text=ends)
    frames = window.locator("iframe")

    def read() -> tuple[list[str], bool]:
        """Every matching body, and whether every iframe has loaded."""
        found = [pre.inner_text().strip() for pre in pres.all()]
        loaded = True
        for frame in frames.all():
            text = frame.content_frame.locator("body").inner_text().strip()
            if not text:
                loaded = False
            elif ends.search(text):
                found.append(text)
        return found, loaded

    def settled() -> bool:
        found, loaded = read()
        return bool(found) and loaded

    try:
        if frames.count():
            _polls(window, settled)
        found, _ = read()
    except PlaywrightError:
        raise UnexpectedScreen("Note body not readable") from None
    if len(found) != 1:
        raise UnexpectedScreen("Note body not found once")
    return found[0]


@dataclass(frozen=True)
class Pdf:
    """The one downloaded PDF, in memory only (D2)."""

    file_name: str
    data: bytes = field(repr=False)


def _download_links(window: Locator) -> Locator:
    return window.get_by_role("link", name="Download document", exact=True)


def attachment_names(window: Locator) -> tuple[str, ...]:
    """Each "Download document" link's URL file_name (URL-decoded), "" when
    it has none. The link's name is only "Download document" (row 02)."""
    try:
        hrefs = [
            link.get_attribute("href") or "" for link in _download_links(window).all()
        ]
    except PlaywrightError:
        raise UnexpectedScreen("attachment not readable") from None
    names = (parse_qs(urlsplit(href).query).get("file_name", []) for href in hrefs)
    return tuple(found[0] if len(found) == 1 else "" for found in names)


def download_pdf(guard: ActionGuard, page: Page, window: Locator) -> Pdf | None:
    """The links are counted first: None, with no click, unless there is
    exactly one and its file_name ends .pdf (any case); decide() gives the
    skip reason (NO_PDF, MULTIPLE_PDFS). Else the click inside
    expect_download, the first file read into memory and deleted at once.
    A second download is deleted unread by note_downloads. Never the preview
    window."""
    names = attachment_names(window)
    if len(names) != 1 or not names[0].lower().endswith(".pdf"):
        return None
    try:
        with page.expect_download(timeout=LOAD_TIMEOUT_MS) as info:
            guard.act("download_attachment", window, _download_links(window))
        download = info.value
        try:
            data = Path(download.path()).read_bytes()
        finally:
            download.delete()
        downloaded = download.suggested_filename
    except (PlaywrightError, OSError):
        raise UnexpectedScreen("PDF did not download") from None
    if downloaded != names[0]:
        raise UnexpectedScreen("download not the linked file")
    return Pdf(file_name=downloaded, data=data)


@contextmanager
def note_downloads(page: Page, folder: Path) -> Iterator[None]:
    """One Note's downloads: when the Note ends, even by an exception, every
    download it fired is deleted and the folder emptied (D2)."""
    seen: list[Download] = []

    def record(download: Download) -> None:
        seen.append(download)

    page.on("download", record)
    try:
        yield
    finally:
        page.remove_listener("download", record)
        for download in seen:
            try:
                download.delete()
            except PlaywrightError:
                pass
        for path in folder.rglob("*"):
            if path.is_file():
                path.unlink(missing_ok=True)


# Project reads (rows 06, 07, 10, 25, 26)

SELECT_TASK = "-- Select Task --"
TASK_OPTION = re.compile(r"^\((tsk_\d+)\) \[Compaction Test\]$")


def task_rows(window: Locator) -> list[list[str]]:
    """The Tasks table's rows as cell texts (header and details rows), in one
    call: a row's innerText holds its cells separated by tabs. Seam 2 (6 Nov
    2026): one call per row took 8-11 s for 74 rows, too slow for the
    settled read's 15 s, and W2 stopped with NO_NEW_TASK."""
    try:
        return [
            [c.strip() for c in text.split("\t")]
            for text in window.locator("tbody tr").all_inner_texts()
        ]
    except PlaywrightError:
        raise UnexpectedScreen("task table not readable") from None


def _task_options(window: Locator) -> set[str]:
    """The Compaction Test numbers in the window's "-- Select Task --" select
    (one option per task, cancelled ones too, row 10)."""
    placeholder = window.page.locator("option").filter(has_text=_exact(SELECT_TASK))
    select = window.locator("select").filter(has=placeholder)
    if select.count() != 1:
        raise UnexpectedScreen("task select not found once")
    options = set()
    for text in select.locator("option").all_inner_texts():
        match = TASK_OPTION.fullmatch(" ".join(text.split()))
        if match:
            options.add(match.group(1))
    return options


def settled_tasks(window: Locator) -> dict[str, str]:
    """Task number -> Status of every Compaction Test task, from a settled
    table: the window shows before its task rows render (row 10, live S6),
    so an empty read can't be told from "no tasks". Tasks count once two
    reads in a row are equal and match the select's options (decisions, 3
    Nov 2026, M4 gate). The rows and the options render together and an
    empty project shows nothing else (probe, 4 Nov 2026), so "no tasks"
    counts only when every read for the full 15 s is empty. Otherwise after
    15 s UnexpectedScreen."""
    deadline = time.monotonic() + LOAD_TIMEOUT_MS / 1000
    last = None
    empty_throughout = True
    while True:
        try:
            tasks = rules.compaction_tasks(task_rows(window))
            whole = set(tasks) == _task_options(window)
        except (PartialWrite, UnexpectedScreen, PlaywrightError):
            tasks, whole = None, False  # a half-rendered row
        if whole and tasks:
            if tasks == last:
                return tasks
            last = tasks
        else:
            last = None
        if not (whole and not tasks):
            empty_throughout = False
        if time.monotonic() >= deadline:
            if empty_throughout:
                return {}
            raise UnexpectedScreen("task table did not settle")
        window.page.wait_for_timeout(POLL_MS)


def project_lookup(
    guard: ActionGuard,
    page: Page,
    base_url: str,
    username: str,
    password: str,
    internal_no: str,
    site: Site,
) -> MySysLookup:
    """Steps 8-10's reads (see _lookup_and_window)."""
    lookup, _ = _lookup_and_window(
        guard, page, base_url, username, password, internal_no, site
    )
    return lookup


def reopen_project(
    guard: ActionGuard,
    page: Page,
    base_url: str,
    username: str,
    password: str,
    proceed: Proceed,
    site: Site,
) -> Locator:
    """W1's reopen (the assignee check reloaded, so step 10's window is
    gone): the same reads as step 10, and the project must still be the
    one decided: the match is the Proceed's pln, Client Internal No. passes
    the match rule and the settled Compaction Test tasks are the Proceed's
    (none created meanwhile). Any mismatch -> WriteNotStarted."""
    lookup, window = _lookup_and_window(
        guard,
        page,
        base_url,
        username,
        password,
        proceed.internal_no,
        site,
        decided_pln=proceed.pln,
    )
    if window is None or check_project(lookup, proceed.internal_no, site) != (
        proceed.pln
    ):
        raise WriteNotStarted("project not as decided", step="W1")
    if {task.task_no for task in lookup.tasks} != set(proceed.existing_task_nos):
        raise WriteNotStarted("project tasks changed since step 10", step="W1")
    # Step 10 passed, so each was Cancelled; one live again (Undo
    # Cancellation meanwhile) would make this booking a duplicate.
    if rules.live_tasks({task.task_no: task.status for task in lookup.tasks}):
        raise WriteNotStarted("project tasks changed since step 10", step="W1")
    return window


def _lookup_and_window(
    guard: ActionGuard,
    page: Page,
    base_url: str,
    username: str,
    password: str,
    internal_no: str,
    site: Site,
    *,
    decided_pln: str | None = None,
) -> tuple[MySysLookup, Locator | None]:
    """Steps 8-10's reads: reload (the Note window would cover the results,
    row 25), Project -> Projects, the demo's search (Enter), every row on
    page 1; match_project() chooses the row, opened by its pln link; then its
    Client Internal No., Address and settled Compaction Test tasks. With no
    single match nothing is opened, the project fields stay empty and the
    window is None. With `decided_pln` (W1's reopen), a match that isn't it
    is WriteNotStarted before anything is opened."""
    from po_agent.mysys import booking  # booking imports this module

    reload_home(guard, page, base_url, username, password)
    panel = booking.open_projects(guard, page)
    rows, pages = booking.search_project_rows(guard, page, panel, internal_no)
    try:
        search_rows = tuple(
            SearchRow(
                pln=row["Project No."],
                client_ref_no=row["Client Ref No."],
                company=row["Company"],
            )
            for row in rows
        )
    except KeyError:
        raise UnexpectedScreen("Projects columns not recognised") from None
    more_pages = pages > 1
    pln = match_project(search_rows, more_pages, internal_no, site)
    if isinstance(pln, Skip):
        return MySysLookup(search_rows=search_rows, more_pages=more_pages), None
    if decided_pln is not None and pln != decided_pln:
        raise WriteNotStarted("project not as decided", step="W1")
    project = booking.open_project(guard, page, panel, pln)
    tasks = settled_tasks(project)
    lookup = MySysLookup(
        search_rows=search_rows,
        more_pages=more_pages,
        project_internal_no=booking.client_internal_no(project),
        address=_labelled(project, "Address:"),
        tasks=tuple(
            CompactionTask(task_no=task_no, status=status)
            for task_no, status in tasks.items()
        ),
    )
    return lookup, project

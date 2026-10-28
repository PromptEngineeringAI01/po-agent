"""The supervised demo's screens: Note window, Projects, Create New Task,
Hold, Link to Project and Solved (decisions, 27 Oct 2026).

Built from docs/screen-map.md v1.2 (rows 02-14, 15b, 25-28) and the 16 Oct
captures, and SPEC.md -> MySys screen rules. Every page action goes through
the guard; everything else here only reads. Each window is the innermost
visible element that holds its heading and one control only it has, so a
minimised copy or a hidden twin is never in scope. Fields with no accessible
name are found by their visible label inside their window (open item 8);
never by generated id or position.

Not mapped (screen-map open item 5): the Link to Project search screens. The
demo snapshots the page right after "Link to Project" so they can be mapped;
a wrong guess here is a guard refusal or a timeout, never a wrong click.

Reads that fail become a fixed `UnexpectedScreen` (or `WriteNotStarted` /
`PartialWrite` for a failed check), never a Playwright message or page text.
"""

import re
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page

from po_agent.b1 import reader_rules as rules
from po_agent.core import output
from po_agent.core.errors import PartialWrite, UnexpectedScreen, WriteNotStarted
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard

LOAD_TIMEOUT_MS = driver.LOAD_TIMEOUT_MS
POLL_MS = 500
# Live 28 Oct 2026: the Choose Project window's content showed only
# after a 15 s wait had given up.
LINK_TIMEOUT_MS = 60_000
# The Projects search: Joey saw pauses of about 10 s (28 Oct 2026).
SEARCH_TIMEOUT_MS = 60_000
OPEN_TRIES = 4  # x 15 s
CREATOR = "Perth Scheduling"
HOLD_NOTE = "ON HOLD UNTIL CALL UP"
REMINDER = "Send me a reminder email every days"
OFFICE = "Prompt Engineering Pty Ltd"
NOT_CHOSEN = "Choose..."
SELECT_USER = "--Select User--"
SELECT_POOL = "--Select Pool--"
ALL_POOLS = "All Pools"
ALL_LOCKED = "All"
PROJECTS_NO_RECORD = "No record found."
NEW_TASK_STATUSES = ("New Project", "Inspection Analysis")
SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "private" / "captures" / "test"


# Finding windows and fields


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


def _container(window: Locator, label: str, control: str) -> Locator:
    """The innermost element in `window` holding the label text and a
    `control` (CSS), e.g. the "PO Number" row and its input. Built from the
    page root: a has_not locator is evaluated inside each candidate."""
    page = window.page
    found = (
        page.locator("*")
        .filter(has=page.get_by_text(label, exact=True))
        .filter(has=page.locator(control))
    )
    return window.locator("*").and_(found.filter(has_not=found))


def _field(window: Locator, label: str, control: str) -> Locator:
    return _container(window, label, control).locator(control)


def _chosen(select: Locator) -> str:
    return (select.locator("option:checked").text_content() or "").strip()


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


def _shows(locator: Locator, timeout: int | None = None) -> bool:
    """Waits (the page's default timeout, else `timeout`) for one element."""
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except PlaywrightError:
        return False


def _gone(locator: Locator) -> bool:
    try:
        locator.wait_for(state="detached", timeout=LOAD_TIMEOUT_MS)
        return True
    except PlaywrightError:
        return False


def save_snapshot(page: Page, step: str) -> Path | None:
    """The page's ARIA snapshot to private/captures/test/demo-<step>.yml
    (real data: laptop only, never committed). Best effort: None on failure."""
    try:
        snapshot = page.locator("body").aria_snapshot()
        # A page's snapshot shows a child frame only as "- iframe".
        for frame in page.frames[1:]:
            inner = frame.locator("body").aria_snapshot()
            snapshot += f"\n# frame {frame.name or '(no name)'}\n{inner}"
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SNAPSHOT_DIR / f"demo-{step}.yml"
        path.write_text(snapshot, encoding="utf-8")
        return path
    except (PlaywrightError, OSError):
        return None


# Note window (rows 02-04, 13-15b)


def note_window(page: Page, note_id: str) -> Locator:
    heading = page.get_by_role(
        "heading", name=re.compile(rf"^Note {re.escape(note_id)} - ")
    )
    return _innermost(page, heading, page.get_by_role("group", name="Status buttons"))


def leave_menu(guard: ActionGuard, page: Page) -> None:
    """Moves the pointer off the header after a Project menu choice.

    Root cause of "page blocked" (27-28 Oct 2026): Playwright's pointer stays
    where its last click left it, in the header; while the header is hovered
    the page covers the body and takes no click below it ("<body> intercepts
    pointer events"). A click elsewhere in the header keeps it there. So the
    guard moves the pointer, with no click, onto the list's status line below
    the header (move_pointer_off_menu; decisions, 28 Oct 2026)."""
    status = (
        page.get_by_text(driver.FOOTER)
        .or_(page.get_by_text(driver.NO_RECORD, exact=True))
        .or_(page.get_by_text(PROJECTS_NO_RECORD, exact=True))
        .visible
    )
    if not _shows(status, LOAD_TIMEOUT_MS):
        raise UnexpectedScreen("list status line not shown")
    guard.act("move_pointer_off_menu", page.locator("body"), status)
    item = driver._project_menu(page).get_by_text("Note Pool", exact=True)
    try:
        item.wait_for(state="hidden", timeout=LOAD_TIMEOUT_MS)
    except PlaywrightError:
        raise UnexpectedScreen("Project menu did not close") from None


def _open(guard: ActionGuard, action: str, scope: Locator, target: Locator) -> None:
    """An opening, searching or refreshing click (it changes nothing in
    MySys), tried OPEN_TRIES times in case the page is still covered (see
    leave_menu). Playwright never clicks while the target is covered, so a
    retry can't act twice. A guard refusal is never retried."""
    for attempt in range(OPEN_TRIES):
        try:
            guard.act(action, scope, target)
            return
        except UnexpectedScreen:
            if attempt == OPEN_TRIES - 1:
                raise
            output.info("demo: page blocked, retrying")


def open_note(guard: ActionGuard, page: Page, panel: Locator, note_id: str) -> Locator:
    """Opens the Note from its Note Pool row by the row's ID cell."""
    _open(
        guard, "open_note", panel, panel.get_by_role("cell", name=note_id, exact=True)
    )
    window = note_window(page, note_id)
    if not _shows(window, LOAD_TIMEOUT_MS):
        raise UnexpectedScreen("Note window did not open")
    return window


def read_assignee(window: Locator) -> str:
    return _labelled(window, "Assignee:")


def read_status(window: Locator) -> str:
    return _labelled(window, "Status:")


def has_link_to_project(window: Locator) -> bool:
    """Step 2a: not linked yet (no project button, no Change Project)."""
    try:
        link = window.get_by_role("button", name="Link to Project", exact=True)
        change = window.get_by_role("button", name="Change Project", exact=True)
        return link.count() == 1 and change.count() == 0
    except PlaywrightError:
        raise UnexpectedScreen("Note window not readable") from None


def _email_box(window: Locator) -> Locator:
    return window.get_by_role("checkbox", name="Send Email Notification", exact=True)


def _email_unticked(window: Locator) -> None:
    try:
        ticked = _email_box(window).is_checked()
    except PlaywrightError:
        raise UnexpectedScreen("Send Email Notification not readable") from None
    if ticked:
        raise UnexpectedScreen("Send Email Notification still ticked")


def untick_send_email(guard: ActionGuard, window: Locator) -> None:
    """Unticks Send Email Notification (ticked whenever a Note window opens)
    and reads it back unticked."""
    try:
        ticked = _email_box(window).is_checked()
    except PlaywrightError:
        raise UnexpectedScreen("Send Email Notification not readable") from None
    if ticked:
        guard.act("untick_send_email_notification", window, _email_box(window))
    _email_unticked(window)


def _list(window: Locator, placeholder: str) -> Locator:
    # Row 26: the Note window's select that holds the placeholder option.
    option = window.page.locator("option").filter(has_text=_exact(placeholder))
    return window.locator("select").filter(has=option)


def _reads(window: Locator, label: str, wanted: str) -> bool:
    """Polls a label until it reads `wanted`, for up to 15 s; a label that
    is gone for a moment (the window re-rendering) is read again."""
    deadline = time.monotonic() + LOAD_TIMEOUT_MS / 1000
    while True:
        try:
            if _labelled(window, label) == wanted:
                return True
        except UnexpectedScreen:
            pass
        if time.monotonic() >= deadline:
            return False
        window.page.wait_for_timeout(POLL_MS)


def _assign(guard: ActionGuard, window: Locator, assignee: str) -> None:
    """Assign, then wait for "Assignee:" to read `assignee`."""
    _email_unticked(window)  # right before the committing click
    guard.act(
        "assign_note", window, window.get_by_role("button", name="Assign", exact=True)
    )
    if not _reads(window, "Assignee:", assignee):
        raise UnexpectedScreen("assignee did not read back")
    _email_unticked(window)


def take_note(guard: ActionGuard, window: Locator, agent: str) -> None:
    """Step 2: Send Email unticked, user list = the agent, pool list left at
    --Select Pool--, Assign; read back the assignee."""
    untick_send_email(guard, window)
    guard.act("select_note_user", window, _list(window, SELECT_USER), agent)
    try:
        pool = _chosen(_list(window, SELECT_POOL))
    except PlaywrightError:
        raise UnexpectedScreen("pool list not readable") from None
    if pool != SELECT_POOL:
        raise UnexpectedScreen("pool list not at its placeholder")
    _assign(guard, window, agent)


def return_note(guard: ActionGuard, window: Locator, pool: str) -> None:
    """Row 15b: one Assign with --Select User-- and the pool."""
    untick_send_email(guard, window)
    guard.act("select_note_user", window, _list(window, SELECT_USER), SELECT_USER)
    guard.act("select_note_pool", window, _list(window, SELECT_POOL), pool)
    _assign(guard, window, pool)


def download_hrefs(window: Locator) -> list[str]:
    links = window.get_by_role("link", name="Download document", exact=True)
    try:
        return [link.get_attribute("href") or "" for link in links.all()]
    except PlaywrightError:
        raise UnexpectedScreen("attachment not readable") from None


def note_body(window: Locator, file_name: str) -> str:
    """The Note's body (row 02): the <pre> in the window whose text ends with
    the file name (27 Oct 2026; the title heading and the file-name <span>
    end with it too). Untrusted data: never printed."""
    ends = re.compile(rf"{re.escape(file_name)}\s*$")
    body = window.locator("pre").filter(has_text=ends)
    try:
        if body.count() != 1:
            raise UnexpectedScreen("Note body not found once")
        return body.inner_text().strip()
    except PlaywrightError:
        raise UnexpectedScreen("Note body not readable") from None


def download_pdf(guard: ActionGuard, page: Page, window: Locator) -> tuple[str, bytes]:
    """Step 3: the "Download document" click inside expect_download; the file
    is read into memory and deleted at once (D2). Returns its suggested name
    and bytes. A second download, if the click fires one, is left in the
    run's download folder, which the demo removes when it ends."""
    link = window.get_by_role("link", name="Download document", exact=True)
    try:
        with page.expect_download(timeout=LOAD_TIMEOUT_MS) as info:
            guard.act("download_attachment", window, link)
        download = info.value
        try:
            data = Path(download.path()).read_bytes()
        finally:
            download.delete()
        return download.suggested_filename, data
    except (PlaywrightError, OSError):
        raise UnexpectedScreen("PDF did not download") from None


def mark_solved(guard: ActionGuard, window: Locator, agent: str) -> None:
    """Step 9: Solved; read back "Solved by <agent>" and Solved disabled."""
    untick_send_email(guard, window)
    _email_unticked(window)
    solved = window.get_by_role("button", name="Solved", exact=True)
    guard.act("mark_solved", window, solved)
    if not _reads(window, "Status:", f"Solved by {agent}"):
        raise PartialWrite("Solved did not read back")
    try:
        if solved.is_enabled():
            raise PartialWrite("Solved did not read back")
    except PlaywrightError:
        raise PartialWrite("Solved did not read back") from None


def find_note_again(
    guard: ActionGuard, page: Page, base_url: str, note_id: str
) -> Locator:
    """SPEC.md -> Finding a Note again: reload, Note Pool under All Pools and
    All, search the Note ID (fill, then Refresh), the row whose ID cell equals
    it, opened."""
    driver.go_home(page, base_url)
    panel = driver.open_note_pool(guard, page)
    leave_menu(guard, page)
    driver._set_filter(guard, panel, "set_pool_filter", driver.POOL_FILTER, ALL_POOLS)
    driver._set_filter(
        guard, panel, "set_locked_filter", driver.LOCK_FILTER, ALL_LOCKED
    )
    search = panel.get_by_role("textbox", name="Search/filter", exact=True)
    guard.act("search_note_pool", panel, search, note_id)
    try:
        before = driver._first_row(panel)
    except PlaywrightError:
        raise UnexpectedScreen("Note Pool list not readable") from None
    refresh = panel.get_by_role("button", name="Refresh", exact=True)
    _open(guard, "refresh_note_pool", panel, refresh)
    driver.wait_for_list(panel, before)
    listing = driver.read_note_pool(guard, panel)
    if [row.note_id for row in listing.rows].count(note_id) != 1:
        raise UnexpectedScreen("Note not found again")
    return open_note(guard, page, panel, note_id)


# Link to Project (row 13; its window seen live on 28 Oct 2026)

CHOOSE_PROJECT = "Choose Project"


def choose_project_window(page: Page) -> Locator:
    """Live S8 (28 Oct 2026): "Link to Project" opens a floating window with
    heading "Choose Project" and textboxes "Search/filter", "After..." and
    "Before..."; its results show only after a search. The heading shows
    before the boxes, and the Note Pool panel has a "Search/filter" too, so
    the window is anchored on "After...", which only it has (live probe,
    12:28: heading + any Search/filter matched an ancestor of both)."""
    return _innermost(
        page,
        page.get_by_role("heading", name=CHOOSE_PROJECT, exact=True),
        page.get_by_role("textbox", name="After...", exact=True),
    )


def _still_open(picker: Locator, page: Page, step: str, snapshots: bool) -> None:
    """After each sub-step: Choose Project is still there (else stop), and,
    in the probe, a snapshot named for the sub-step."""
    if snapshots:
        save_snapshot(page, f"probe-link-{step}")
    try:
        open_now = picker.count() == 1
    except PlaywrightError:
        open_now = False
    if not open_now:
        raise UnexpectedScreen("Choose Project not open")


def _link_choice(picker: Locator, pln: str) -> Locator:
    """The one result naming the pln: a link, button, cell or text. The
    results were not seen live yet: the demo snapshots them (S8-link-results)."""
    candidates = (
        picker.get_by_role("link", name=pln, exact=True),
        picker.get_by_role("button", name=pln, exact=True),
        picker.get_by_role("cell", name=pln, exact=True),
        picker.get_by_text(pln, exact=True),
    )
    if not _shows(candidates[-1].first, LINK_TIMEOUT_MS):
        raise UnexpectedScreen("project not listed in Choose Project")
    save_snapshot(picker.page, "S8-link-results")
    for choice in candidates:
        if choice.visible.count() == 1:
            return choice
    raise UnexpectedScreen("project not listed once in Choose Project")


def _search_choose_project(
    guard: ActionGuard, page: Page, window: Locator, pln: str, snapshots: bool
) -> Locator:
    """Send Email unticked, Link to Project, then in Choose Project (up to
    60 s to load): fill its own Search/filter with the pln and run the search.
    Only reads and opens: nothing is linked until a result is selected."""
    untick_send_email(guard, window)
    link = window.get_by_role("button", name="Link to Project", exact=True)
    guard.act("link_to_project", window, link)
    picker = choose_project_window(page)
    if not _shows(picker, LINK_TIMEOUT_MS):
        save_snapshot(page, "S8-link-opened")
        raise UnexpectedScreen("Link to Project search did not show")
    _still_open(picker, page, "1-opened", snapshots)
    search = picker.get_by_role("textbox", name="Search/filter", exact=True)
    guard.act("link_search_project", picker, search, pln)
    _still_open(picker, page, "2-filled", snapshots)
    guard.act("submit_link_search", picker, search, "Enter")  # Joey, 28 Oct
    _still_open(picker, page, "3-searched", snapshots)
    return picker


def probe_link(guard: ActionGuard, page: Page, window: Locator, pln: str) -> None:
    """--probe-link: open Choose Project, search the pln, snapshot each
    sub-step and the results (demo-probe-link-*.yml), select nothing; stops
    with UnexpectedScreen if the window closes or the pln isn't listed. The
    demo then abandons the window by closing the browser."""
    picker = _search_choose_project(guard, page, window, pln, snapshots=True)
    listed = _shows(picker.get_by_text(pln, exact=True).first, LINK_TIMEOUT_MS)
    save_snapshot(page, "probe-link-results")
    if not listed:
        raise UnexpectedScreen("project not listed in Choose Project")


def link_project(guard: ActionGuard, page: Page, window: Locator, pln: str) -> None:
    """Step 8: Link to Project -> Choose Project: search the pln, run the
    search (a click on the window's heading moves focus, as the Note Pool's
    search runs when focus leaves the box), select the pln; read back the
    Note's project button and a Status that still starts "Pending" (live it
    reads "Pending by <agent>")."""
    picker = _search_choose_project(guard, page, window, pln, snapshots=False)
    choice = _link_choice(picker, pln)
    _email_unticked(window)
    guard.act("link_select_project", picker, choice)
    if not _shows(window.get_by_role("button", name=pln, exact=True), LOAD_TIMEOUT_MS):
        raise PartialWrite("project link did not read back")
    if not read_status(window).startswith("Pending"):
        raise PartialWrite("Note status not Pending after linking")


# Projects (rows 06, 07, 16, 25, 26)


def projects_panel(page: Page) -> Locator:
    """Row 26: the panel holding Reset Filter, Search..., All Projects and the
    results list."""
    return _innermost(
        page,
        page.get_by_role("button", name="Reset Filter", exact=True),
        page.get_by_role("textbox", name="Search...", exact=True),
        page.locator("option").filter(has_text=_exact("All Projects")),
        # and the list, as driver.note_pool_panel: the filters alone are a
        # smaller block that doesn't hold the results.
        page.locator("table").or_(page.get_by_text(PROJECTS_NO_RECORD, exact=True)),
    )


def open_projects(guard: ActionGuard, page: Page) -> Locator:
    """Project menu -> Projects, as driver.open_note_pool does Note Pool."""
    menu = driver._project_menu(page)
    title = driver._project_title(page)
    item = menu.get_by_text("Projects", exact=True)
    for _ in range(driver.MENU_TRIES):
        guard.act("open_project_tab", menu, title)
        driver._network_idle(page)
        if _shows(item, 2000):
            break
    else:
        raise UnexpectedScreen("Projects menu item did not show")
    guard.act("open_projects_subtab", menu, item)
    leave_menu(guard, page)
    panel = projects_panel(page)
    if not _shows(panel, LOAD_TIMEOUT_MS):
        raise UnexpectedScreen("Projects panel did not show")
    return panel


def _table(container: Locator) -> list[dict[str, str]]:
    headers = [h.strip() for h in container.locator("thead th").all_inner_texts()]
    rows = []
    for row in container.locator("tbody tr").all():
        cells = [c.strip() for c in row.locator("td").all_inner_texts()]
        if len(cells) != len(headers):
            raise UnexpectedScreen("Projects row not recognised")
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


# Each Projects filter select, by the default option only it holds (row 26:
# they have no name), and its field identifier.
PROJECT_FILTERS = {
    "All Projects": "status",
    "All Eng Types": "eng_type",
    "All Sales Types": "sales_type",
}


def _check_project_filters(panel: Locator) -> None:
    """Every Projects filter at its default, so none hides the project (a
    Status other than All Projects could hide a Cancelled one). Read only:
    the agent never changes them.

    Live S5 (28 Oct 2026, 14:06): the labels and controls share one block,
    so a label can't scope its control. Each select is found by its default
    option; every textbox but the search box (Company "Select...", the two
    dates) must be empty."""
    page = panel.page
    try:
        for default, field in PROJECT_FILTERS.items():
            option = page.locator("option").filter(has_text=_exact(default))
            select = panel.locator("select").filter(has=option)
            if select.count() != 1:
                raise UnexpectedScreen("Projects filter not found once", field=field)
            if _chosen(select) != default:
                raise UnexpectedScreen(
                    "Projects filter not at its default", field=field
                )
        search = panel.get_by_role("textbox", name="Search...", exact=True)
        for box in panel.get_by_role("textbox").all():
            if box.and_(search).count() == 0 and box.input_value():
                raise UnexpectedScreen("Projects text filter not empty")
    except PlaywrightError:
        raise UnexpectedScreen("Projects filters not readable") from None


def _project_list(panel: Locator) -> tuple | None:
    """The list as a hashable state: ("none",) for "No record found.",
    ("rows", rows, pages) for rows under a recognised footer, None while it
    reloads (a loading row, no footer, a re-render under the read)."""
    try:
        if panel.get_by_text(PROJECTS_NO_RECORD, exact=True).visible.count():
            return ("none",) if panel.locator("tbody tr").count() == 0 else None
        footer = panel.get_by_text(driver.FOOTER).visible
        if footer.count() != 1:
            return None
        match = driver.FOOTER.match((footer.text_content() or "").strip())
        if match is None:
            return None
        rows = tuple(tuple(row.items()) for row in _table(panel))
    except (PlaywrightError, UnexpectedScreen):
        return None
    return ("rows", rows, int(match.group(2)))


def search_projects(
    guard: ActionGuard, page: Page, panel: Locator, internal_no: str
) -> list[dict[str, str]]:
    """Step 5: fill Search... with the internal number, press Enter (Joey,
    28 Oct 2026), then wait up to 60 s for the list to settle on its result.

    Ways the search could miss a project that exists, and what this does:
    the old list (or a stale "No record found.") is still showing -> only a
    list that differs from it, or whose rows all hold the number, counts; a
    loading row or a re-render mid-read -> read again; a slow load -> 60 s,
    not 15; a hit on a field not shown -> any settled list counts, and
    match_project picks the row; the same row twice -> match_project counts
    projects, not rows; a filter left set -> refused before searching. A
    settled list is the same in two reads in a row. More than one results
    page counts as ambiguous."""
    _check_project_filters(panel)
    before = _project_list(panel)
    search = panel.get_by_role("textbox", name="Search...", exact=True)
    guard.act("search_project", panel, search, internal_no)
    guard.act("submit_project_search", panel, search, "Enter")
    wanted = internal_no.lower()
    deadline = time.monotonic() + SEARCH_TIMEOUT_MS / 1000
    last = None
    while True:
        state = _project_list(panel)
        holds_it = (
            state is not None
            and state[0] == "rows"
            and all(
                wanted in " ".join(value for _, value in row).lower()
                for row in state[1]
            )
        )
        if state is not None and (state != before or holds_it):
            if state == last:
                if state[0] == "none":
                    return []
                if state[2] > 1:
                    raise WriteNotStarted(
                        "project ambiguous", reason="PROJECT_AMBIGUOUS"
                    )
                return [dict(row) for row in state[1]]
            last = state
        else:
            last = None
        if time.monotonic() >= deadline:
            raise UnexpectedScreen("project search did not finish")
        page.wait_for_timeout(POLL_MS)


def project_window(page: Page, pln: str) -> Locator:
    heading = page.get_by_role("heading", name=re.compile(rf"^{re.escape(pln)} "))
    create = page.get_by_role("button", name="Create New Task", exact=True)
    return _innermost(page, heading, create)


def open_project(guard: ActionGuard, page: Page, panel: Locator, pln: str) -> Locator:
    _open(guard, "open_project", panel, panel.get_by_role("link", name=pln, exact=True))
    window = project_window(page, pln)
    if not _shows(window, LOAD_TIMEOUT_MS):
        raise UnexpectedScreen("project window did not open")
    return window


def client_internal_no(window: Locator) -> str:
    return _labelled(window, "Client Internal No.:")


def task_rows(window: Locator) -> list[list[str]]:
    """The Tasks table's rows as cell texts (header and details rows)."""
    try:
        return [
            [c.strip() for c in row.locator("td").all_inner_texts()]
            for row in window.locator("tbody tr").all()
        ]
    except PlaywrightError:
        raise UnexpectedScreen("task table not readable") from None


# Create New Task (rows 08-10)


def task_form(page: Page) -> Locator:
    return _innermost(
        page,
        page.get_by_role("heading", name="Create New Task", exact=True),
        page.get_by_role("button", name="Submit", exact=True),
    )


def open_task_form(guard: ActionGuard, page: Page, project: Locator) -> Locator:
    create = project.get_by_role("button", name="Create New Task", exact=True)
    guard.act("open_create_new_task", project, create)
    form = task_form(page)
    if not _shows(form, LOAD_TIMEOUT_MS):
        raise WriteNotStarted("Create New Task did not open")
    return form


def fill_task_form(
    guard: ActionGuard,
    form: Locator,
    po_number: str,
    body: str,
    file_name: str,
    data: bytes,
) -> None:
    """Step 6 up to Submit: Creator, - Compaction Test, PO Number, the PDF to
    PO Documents from memory, Note = the email body; then every read-back."""
    guard.act("set_creator", form, _field(form, "Creator", "select"), CREATOR)
    compaction = form.get_by_role("checkbox", name="- Compaction Test", exact=True)
    guard.act("tick_compaction_test", form, compaction)
    po_box = _field(form, "PO Number", "input")
    if not _shows(po_box, LOAD_TIMEOUT_MS):
        raise WriteNotStarted("Compaction Test form did not open")
    guard.act("set_po_number", form, po_box, po_number)
    upload = _field(form, "PO Documents", 'input[type="file"]')
    payload = {"name": file_name, "mimeType": "application/pdf", "buffer": data}
    guard.act("upload_document", form, upload, payload)
    guard.act("set_task_note", form, _field(form, "Note", "textarea"), body)
    check_task_form(form, po_number, body, file_name)


def check_task_form(form: Locator, po_number: str, body: str, file_name: str) -> None:
    """Row 09 read-back before Submit; any mismatch -> WriteNotStarted."""
    po_docs = _container(form, "PO Documents", 'input[type="file"]')
    if not _shows(po_docs.get_by_text(file_name, exact=True), LOAD_TIMEOUT_MS):
        raise WriteNotStarted("task form not as expected", field="po_documents")
    try:
        checks = {
            "creator": _chosen(_field(form, "Creator", "select")) == CREATOR,
            "ticked": form.get_by_role("checkbox", checked=True).count() == 1
            and form.get_by_role(
                "checkbox", name="- Compaction Test", exact=True
            ).is_checked(),
            "task_client": "Same as Project"
            in _container(form, "Task Client", "button").inner_text(),
            "task_name": form.get_by_role(
                "textbox", name="Task Name", exact=True
            ).input_value()
            == "",
            "po_number": _field(form, "PO Number", "input").input_value() == po_number,
            "po_documents": po_docs.locator("tr").count() == 1,
            "documents": _container(form, "Documents", 'input[type="file"]')
            .locator("tr")
            .count()
            == 0,
            "note": _field(form, "Note", "textarea").input_value() == body,
            "sale_office": _chosen(_field(form, "Sale Office", "select")) == OFFICE,
            "po_contact": _chosen(_field(form, "PO Contact", "select")) == NOT_CHOSEN,
            "delivery_office": _chosen(_field(form, "Delivery Office", "select"))
            == NOT_CHOSEN,
        }
    except PlaywrightError:
        raise WriteNotStarted("task form not readable") from None
    for name, ok in checks.items():
        if not ok:
            raise WriteNotStarted("task form not as expected", field=name)


def submit_task(guard: ActionGuard, form: Locator) -> None:
    guard.act(
        "submit_task", form, form.get_by_role("button", name="Submit", exact=True)
    )


def wait_new_task(form: Locator, project: Locator, before: set[str]) -> str:
    """Row 10: the form closes, then exactly one new Compaction Test task
    shows, with Status New Project or Inspection Analysis.

    Live S6 (28 Oct 2026, 17:15): MySys adds the new task's header row before
    its details row, and the Status cell can fill in later still. A read in
    between is not an answer: the table is read again until the new task is
    whole or 15 s have passed; only then does the last problem stop the run."""
    if not _gone(form):
        raise PartialWrite("Create New Task did not close")
    deadline = time.monotonic() + LOAD_TIMEOUT_MS / 1000
    while True:
        try:
            tasks = rules.compaction_tasks(task_rows(project))
            task_id = rules.new_task(before, tasks)
            if tasks[task_id] not in NEW_TASK_STATUSES:
                raise PartialWrite(
                    "new task status not as expected", reason="TASK_STATUS"
                )
            return task_id
        except (PartialWrite, UnexpectedScreen):
            if time.monotonic() >= deadline:
                raise
        project.page.wait_for_timeout(POLL_MS)


# Hold (rows 11-12)


def _task_header(project: Locator, task_id: str) -> Locator:
    text = project.page.get_by_text(f"({task_id}) | Compaction Test", exact=True)
    return project.get_by_role("row").filter(has=text)


def hold_dialog(page: Page, task_id: str) -> Locator:
    return _innermost(
        page,
        page.get_by_role("heading", name=f"Hold Task: {task_id}", exact=True),
        page.get_by_role("textbox", name="Note", exact=True),
    )


def open_hold(
    guard: ActionGuard, page: Page, project: Locator, task_id: str
) -> Locator:
    """The new task's own Hold (exact name: never Un-Hold)."""
    hold = _task_header(project, task_id).get_by_role("button", name="Hold", exact=True)
    guard.act("open_hold", project, hold)
    dialog = hold_dialog(page, task_id)
    if not _shows(dialog, LOAD_TIMEOUT_MS):
        raise PartialWrite("Hold Task did not open")
    return dialog


def fill_hold(guard: ActionGuard, dialog: Locator) -> None:
    """Types the hold note and touches no checkbox; then reads every check:
    only the reminder ticked, with 0 days, and the note exact."""
    note = dialog.get_by_role("textbox", name="Note", exact=True)
    guard.act("set_hold_note", dialog, note, HOLD_NOTE)
    try:
        checks = {
            "ticked": dialog.get_by_role("checkbox", checked=True).count() == 1,
            "reminder": dialog.get_by_role(
                "checkbox", name=REMINDER, exact=True
            ).is_checked(),
            "reminder_days": dialog.get_by_role("spinbutton").input_value() == "0",
            "note": note.input_value() == HOLD_NOTE,
        }
    except PlaywrightError:
        raise PartialWrite("Hold dialog not readable") from None
    for name, ok in checks.items():
        if not ok:
            raise PartialWrite("Hold dialog not as expected", field=name)


def confirm_hold(guard: ActionGuard, page: Page, dialog: Locator) -> None:
    """The dialog's own Hold (scoped by its "Hold Task: tsk_..." heading)."""
    guard.act(
        "confirm_hold", dialog, dialog.get_by_role("button", name="Hold", exact=True)
    )
    if not _gone(dialog):
        raise PartialWrite("Hold Task did not close")


def check_on_hold(project: Locator, task_id: str) -> None:
    """Row 12: the task's row has Un-Hold and its Status starts On-hold with
    the hold note."""
    un_hold = _task_header(project, task_id).get_by_role(
        "button", name="Un-Hold", exact=True
    )
    if not _shows(un_hold):
        raise PartialWrite("task not on hold")
    status = rules.compaction_tasks(task_rows(project)).get(task_id, "")
    if not status.startswith("On-hold") or HOLD_NOTE not in status:
        raise PartialWrite("task not on hold")

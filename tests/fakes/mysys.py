"""Seam 2's fake MySys: the driver's and the booker's MySys steps, faked at
the module-function seam, for the offline run-loop tests.

Nothing opens a browser: `install` patches every name in `DRIVER_NAMES`
(and, for the booker, `BOOKER_DRIVER_NAMES` and `BOOKING_NAMES`) with a
`FakeMySys` method. The decision engine and both PDF readers run for real
on a fake PDF built by seam 1's `text_pdf` (no committed PDF). The fake
keeps each Note's assignee, so a test can check where every Note ends.

A comment that cites `docs/screen-map.md` (row NN) or `docs/decisions.md`
(date, title) names where a behaviour of the fake comes from. A behaviour
with no such comment has no mapped source. Values are fake.
"""

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest
from seam1.seam1_cases import CASES, text_pdf

from po_agent.core import run
from po_agent.core.errors import UnexpectedScreen
from po_agent.core.models import (
    MySysLookup,
    NotePoolFilters,
    NotePoolRow,
    ProjectTask,
    SearchRow,
)
from po_agent.mysys import booking, driver
from po_agent.mysys.guard import ActionGuard

# The test site's pool (screen-map "Live vs test") and the agent's user name
# (screen-map rows 03-04).
POOL = "Agent Pool"
AGENT = "Agent 1 (MySys Only)"
PERSON = "<a person>"
CLEAN = next(case for case in CASES if case.id == "p1-clean")
FILE = "2600001B_048_1.pdf"  # the attachment's file name (screen-map row 05)
# Both readers read these lines alike (as tests/seam1/test_seam1_real_data.py).
PDF = text_pdf([line for line in CLEAN.pypdf_text.splitlines() if "(" not in line])


@dataclass
class FakeNote:
    """One Note as the fake MySys holds it. `fail_at`, `person_takes_at` and
    `kill_at` name a call ("check": every call of that name) or one call by
    its count for this Note ("check#2": the second)."""

    internal_no: str
    assignee: str = POOL
    linked: bool = False
    names: tuple[str, ...] = (FILE,)
    lookup: MySysLookup = CLEAN.lookup
    body: str = CLEAN.note.body  # what the body read returns
    pdf: bytes = PDF  # the one PDF's bytes, when it downloads
    fail_at: str | None = None  # a call name that raises `fail_with`
    fail_with: type[BaseException] = UnexpectedScreen
    # A call during which a person takes it: the Note Pool list is read once
    # per run, so a person can take a listed Note before the agent reaches it
    # (decisions, 2 Nov 2026, decide-only: how each Note is opened).
    person_takes_at: str | None = None
    kill_at: str | None = None  # a call during which `enabled` is set false
    taken: int = 0


class FakePage:
    """The page `open_browser` yields; closing its context is recorded."""

    def __init__(self, calls: list[str]) -> None:
        self.context = SimpleNamespace(close=lambda: calls.append("context_closed"))


@dataclass
class FakeMySys:
    notes: dict[str, FakeNote]
    rows: tuple[NotePoolRow, ...]
    fail_return: bool = False
    close_fails: bool = False  # closing a browser raises (Chromium gone)
    break_log_at: str | None = None  # a call after which the run log can't be written
    logs_dir: Path | None = None
    # What the stale-Note read (3.6) lists on page 1 of `agent_pages`.
    agent_rows: tuple[NotePoolRow, ...] = ()
    agent_pages: int = 1
    # What live's stale-Note read, My Notes, lists on page 1 of `my_notes_pages`.
    my_notes_rows: tuple[NotePoolRow, ...] = ()
    my_notes_pages: int = 1
    pool_pages: int = 1  # pages of the run's filtered Note Pool read
    config_dir: Path | None = None  # the run's config, for `kill_at`
    task_no: str = "tsk_200002"  # the task the fake Submit creates
    current: str | None = None  # the Note last named in a call
    calls: list[str] = field(default_factory=list)
    downloads: list[Path | None] = field(default_factory=list)
    reads: int = 0
    counts: Counter = field(default_factory=Counter)  # (Note ID, call name)
    # What the run passed in: the Note Pool filters, (Note ID, body rule),
    # (step, project rule), W2's Documents Type (task 9.4: the client's) and
    # (step, agent) where a read-back names the agent.
    filters: list = field(default_factory=list)
    body_rules: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    document_types: list = field(default_factory=list)
    agents: list = field(default_factory=list)
    # With `record_actions`, each fake step appends to the run's guard
    # history the actions the real step takes through guard.act (named after
    # mysys/driver.py and mysys/booking.py), so a test can read which kinds
    # of action a run took. Off: B1's tests see the history as before.
    record_actions: bool = False
    guard: ActionGuard | None = None  # the run's guard, kept at login

    def _acted(self, guard: ActionGuard, *actions: str) -> None:
        if self.record_actions:
            guard.history.extend((action, "done") for action in actions)

    def _note(self, window: str) -> tuple[str, FakeNote]:
        note_id = window.removeprefix("window-")
        return note_id, self.notes[note_id]

    def _call(self, name: str, note_id: str | None = None) -> None:
        self.calls.append(f"{name} {note_id}" if note_id else name)
        if note_id:
            self.current = note_id
            self.counts[note_id, name] += 1
        note = self.notes.get(note_id) if note_id else None
        named = (name, f"{name}#{self.counts[note_id, name]}")
        if note and note.person_takes_at in named:
            note.assignee = PERSON
        if note and note.kill_at in named:
            toml = self.config_dir / "test.toml"
            text = toml.read_text("utf-8")
            assert "enabled = true" in text
            toml.write_text(text.replace("enabled = true", "enabled = false"), "utf-8")
        if self.break_log_at == name:
            # The run log becomes a folder: the next write raises OSError.
            self.break_log_at = None  # once
            (log,) = self.logs_dir.glob("*.jsonl")
            log.unlink()
            log.mkdir()
        if note and note.fail_at in named:
            if note.fail_with is UnexpectedScreen:
                raise UnexpectedScreen("fake failure", note_id=note_id)
            raise note.fail_with("fake failure")

    @contextmanager
    def open_browser(self, *, headed, slow_mo, downloads=None):
        self.calls.append("open_browser")
        self.downloads.append(downloads)
        try:
            yield FakePage(self.calls)
        finally:
            self.calls.append("closed")
            if self.close_fails:
                raise RuntimeError("fake close failure")

    def go_home(self, page, base_url):
        self.calls.append("go_home")

    def login(self, guard, page, username, password):
        self.calls.append("login")  # Username, Password, "Log in" (screen-map row 26)
        self.guard = guard
        self._acted(guard, "login_username", "login_password", "login_submit")

    def open_note_pool(self, guard, page):
        self.calls.append("open_note_pool")
        self._acted(guard, "open_project_tab", "open_note_pool")
        return "panel"

    def leave_menu(self, guard, page):
        self.calls.append("leave_menu")
        self._acted(guard, "move_pointer_off_menu")

    def set_note_pool_filters(self, guard, panel, filters: NotePoolFilters):
        # The list reloads by itself after a filter change (screen-map row 27).
        self.calls.append("filters")
        self.filters.append(filters)
        chosen = (
            ("set_pool_filter", filters.pool),
            ("set_source_filter", filters.source),
            ("set_locked_filter", filters.locked),
        )
        self._acted(guard, *(action for action, value in chosen if value))

    def read_note_pool(self, guard, panel, *, with_source=False):
        # Page 1 of `pool_pages`, as the footer "Page 1 of N" tells (screen-map
        # row 01); more than one page stops the run (decisions, 5 Nov 2026,
        # silent-skip alert and more pages). `with_source`: the Source column
        # is read too (screen-map row 01's columns; Summit, task 9.11).
        self.reads += 1
        self.calls.append("read with source" if with_source else "read")
        return driver.NotePoolList(
            rows=self.rows, total=len(self.rows), pages=self.pool_pages
        )

    def read_agent_notes(self, guard, panel, agent):
        # The stale-Note read: Pending Notes under All Users, All Pools, page 1
        # only (decisions, 3 Nov 2026, assignee check and stale-Note stop).
        self.calls.append("agent_notes")
        rows = self.agent_rows
        return driver.NotePoolList(rows=rows, total=len(rows), pages=self.agent_pages)

    def reload_home(self, guard, page, base_url, username, password):
        self.calls.append("reload_home")

    def open_my_notes(self, guard, page):
        # Live's stale-Note read (screen-map row 29; decisions, 10 Nov 2026,
        # live stale-Note read from My Notes).
        self.calls.append("open_my_notes")
        self._acted(guard, "open_project_tab", "open_my_notes")
        return "my-notes"

    def read_my_notes(self, panel):
        # The Notes assigned to the logged-in user, page 1 of
        # `my_notes_pages` (screen-map row 29).
        assert panel == "my-notes"
        self.calls.append("my_notes")
        rows = self.my_notes_rows
        return driver.NotePoolList(
            rows=rows, total=len(rows), pages=self.my_notes_pages
        )

    def find_note_again(self, guard, page, base_url, username, password, note_id):
        # The real one reloads base_url first: a reload before every Note
        # (decisions, 2 Nov 2026, decide-only: how each Note is opened;
        # screen-map row 25).
        self._call("find_again", note_id)
        self._acted(
            guard,
            "open_project_tab",
            "open_note_pool",
            "move_pointer_off_menu",
            "set_pool_filter",
            "set_locked_filter",
            "search_note_pool",
            "refresh_note_pool",
            "open_note",
        )
        return f"window-{note_id}"

    def read_assignee(self, window):
        # "Assignee:" in the Note window (screen-map row 02), read from a
        # freshly opened window: an open one does not refresh (row 23).
        note_id, note = self._note(window)
        self._call("assignee", note_id)
        return note.assignee

    def take_note(self, guard, window, agent, log, note_id):
        # After Assign, "Assignee:" reads the agent (screen-map rows 03-04).
        _, note = self._note(window)
        note.taken += 1
        self._call("take", note_id)
        self._acted(
            guard, "untick_send_email_notification", "select_note_user", "assign_note"
        )
        note.assignee = agent

    def is_unlinked(self, window, log, note_id):
        # Step 2a: Link to Project shows until the Note is linked; after, a
        # project button and Change Project (screen-map rows 02, 13).
        _, note = self._note(window)
        self._call("2a", note_id)
        return not note.linked

    def attachment_names(self, window):
        # Each "Download document" link's file_name (screen-map row 02).
        note_id, note = self._note(window)
        self._call("names", note_id)
        return note.names

    @contextmanager
    def note_downloads(self, page, folder):
        yield

    def download_pdf(self, guard, page, window):
        # Exactly one link whose file_name ends .pdf, else no download
        # (screen-map rows 21-23; decisions, 25 Oct 2026, M0b.1).
        note_id, note = self._note(window)
        self._call("download", note_id)
        if len(note.names) != 1 or not note.names[0].lower().endswith(".pdf"):
            return None
        self._acted(guard, "download_attachment")
        return driver.Pdf(file_name=note.names[0], data=note.pdf)

    def note_body(self, window, body):
        # The Note body: B1's one line ending with the file name (screen-map
        # row 02); a Summit Note's, the email iframe's text (SUMMIT_BODY).
        note_id, note = self._note(window)
        self._call("body", note_id)
        self.body_rules.append((note_id, body))
        return note.body

    def project_lookup(
        self, guard, page, base_url, username, password, internal_no, rule
    ):
        # The real one reloads base_url: the Note window is gone after it
        # (screen-map rows 25, 27).
        (note_id,) = [n for n, v in self.notes.items() if v.internal_no == internal_no]
        self._call("lookup", note_id)
        self.rules.append(("lookup", rule))
        self._acted(
            guard,
            "open_project_tab",
            "open_projects_subtab",
            "search_project",
            "submit_project_search",
            "open_project",
        )
        return self.notes[note_id].lookup

    def return_note(self, guard, window, agent, pool, log, note_id):
        # One Assign with --Select User-- and the pool: "Assignee:" reads the
        # pool (screen-map rows 15, 15b).
        _, note = self._note(window)
        self._call("return", note_id)
        self._acted(
            guard,
            "untick_send_email_notification",
            "select_note_user",
            "select_note_pool",
            "assign_note",
        )
        if self.fail_return:
            raise UnexpectedScreen("fake return failure", note_id=note_id)
        note.assignee = pool

    # --- the booker's MySys steps (4.5), named after the Note in hand ------------

    def _step(self, name: str) -> None:
        self._call(name, self.current)

    def search_note(self, guard, page, base_url, username, password, note_id):
        # The assignee check before W1 and W4 (controls.assignee_check): the
        # Note ID searched under All Pools lists its row with its Assignee
        # (screen-map row 27; decisions, 3 Nov 2026, assignee check and
        # stale-Note stop).
        self._call("check", note_id)
        note = self.notes[note_id]
        rows = (row(note_id, note.internal_no, assignee=note.assignee),)
        return "panel", driver.NotePoolList(rows=rows, total=1, pages=1)

    def reopen_project(self, guard, page, base_url, username, password, proceed, rule):
        # The project window (screen-map row 07).
        self._call("reopen", proceed.note_id)
        self.rules.append(("reopen", rule))
        return "project"

    def open_task_form(self, guard, page, project):
        self._step("form")  # Create New Task (screen-map row 08)
        return "form"

    def fill_task_form(self, guard, form, po_number, body, file_name, data, *, creator):
        self._step("fill")  # Compaction Test ticked and filled (screen-map row 09)

    def submit_task(self, guard, form):
        self._step("submit")  # the write (screen-map row 08)
        guard.history.append(("submit_task", "done"))

    def new_task_after_submit(self, form, project, before):
        # One new Compaction Test task on the project (screen-map row 10).
        self._step("new_task")
        return self.task_no

    def check_new_task_row(self, project, task_no, agent, *, creator):
        self._step("task_row")  # the new task's details row (screen-map row 10)
        self.agents.append(("task_row", agent))
        return "details"

    def open_task_detail(self, guard, project, details, *, creator):
        self._step("open_detail")  # opened from the details row (screen-map row 19)

    def check_task_detail(self, page, task_no, po_number, body, agent, *, creator):
        self._step("detail")  # the task detail screen (screen-map row 19)
        self.agents.append(("detail", agent))
        return "detail-window"

    def back_to_project(self, guard, page, window, pln):
        self._step("back")  # "-- Select Task --" (screen-map row 19)

    def check_project_document(
        self, guard, page, pln, task_no, file_name, document_type
    ):
        # The new task's section of the project's Documents tab (screen-map
        # row 19).
        self._step("document")
        self.document_types.append(document_type)

    def project_window(self, page, pln):
        self._step("project_window")  # the project window (screen-map row 07)
        return "project"

    def open_hold(self, guard, page, project, task_no):
        self._step("open_hold")  # the Hold Task dialog (screen-map row 11)
        return "dialog"

    def fill_hold(self, guard, dialog):
        self._step("fill_hold")  # Note = ON HOLD UNTIL CALL UP (screen-map row 11)

    def confirm_hold(self, guard, page, dialog):
        self._step("confirm_hold")  # the dialog's own Hold (screen-map row 11)
        guard.history.append(("confirm_hold", "done"))

    def check_on_hold(self, project, task_no):
        self._step("on_hold")  # Un-Hold and "On-hold" (screen-map row 12)

    def link_project(self, guard, page, window, pln, *, log=None, note_id=None):
        # The real one reads Send Email back unticked right before Link to
        # Project and again right before its committing select, each an
        # `email_notification_unticked` event in `log`, as guard.act records
        # them (decisions, 4 Nov 2026, W4 and W5; 20 Nov 2026, one Send Email
        # control; screen-map rows 13, 20).
        self._step("link")
        for action in ("link_to_project", "link_select_project"):
            _unticked(log, note_id, "W4")
            guard.history.append((action, "done"))

    def log_line_count(self, window):
        self._step("log_count")
        return 0

    def mark_solved(self, guard, window, agent, *, log=None, note_id=None):
        # Send Email read back unticked (an event in `log`), then Solved once
        # (decisions, 4 Nov 2026, W4 and W5; 20 Nov 2026, one Send Email
        # control; screen-map row 14).
        self._step("solved")
        self.agents.append(("solved", agent))
        _unticked(log, note_id, "W5")
        guard.history.append(("mark_solved", "done"))  # as guard.act records it

    def check_solved_log(self, window, before):
        self._step("solved_log")  # "Status changed: ... to Solved" (screen-map row 14)

    def gone_from_pending(self, guard, page, base_url, username, password, note_id):
        # A Solved Note leaves the Pending list (screen-map row 14).
        self._call("gone", note_id)


def _unticked(log, note_id, step):
    # The real check's event for a box read back unticked; at W4 and W5 a
    # run-log write that fails never stops the booking (SPEC -> Safe trace).
    if log is None:
        return
    try:
        log.event("email_notification_unticked", note_id=note_id, step=step, ok=True)
    except OSError:
        pass


DRIVER_NAMES = (
    "open_browser",
    "go_home",
    "login",
    "open_note_pool",
    "leave_menu",
    "set_note_pool_filters",
    "read_note_pool",
    "read_agent_notes",
    "reload_home",
    "open_my_notes",
    "read_my_notes",
    "find_note_again",
    "read_assignee",
    "take_note",
    "is_unlinked",
    "attachment_names",
    "note_downloads",
    "download_pdf",
    "note_body",
    "project_lookup",
    "return_note",
)
# The booker's MySys steps (4.5).
BOOKER_DRIVER_NAMES = (
    "search_note",
    "reopen_project",
    "log_line_count",
    "gone_from_pending",
)
BOOKING_NAMES = (
    "open_task_form",
    "fill_task_form",
    "submit_task",
    "new_task_after_submit",
    "check_new_task_row",
    "open_task_detail",
    "check_task_detail",
    "back_to_project",
    "check_project_document",
    "project_window",
    "open_hold",
    "fill_hold",
    "confirm_hold",
    "check_on_hold",
    "link_project",
    "mark_solved",
    "check_solved_log",
)


def row(note_id: str, internal_no: str, *, assignee=POOL) -> NotePoolRow:
    # Project reads "---" until the Note is linked (screen-map row 01).
    return NotePoolRow(
        note_id=note_id,
        subject_note=f"Please find attached file {internal_no}_048_1.pdf",
        project="---",
        assignee=assignee,
    )


# Summit-shaped Note Pool rows (SPEC.md -> Client 2, Which Notes). Live's
# Note Pool shows a Summit email Note's title alone in Subject/Note and the
# bare sender address in Source (Joey's 23 Nov 2026 screenshot, kept in
# private/summit/). Fake mailbox, sender domain and companies.
SUMMIT_MAILBOX = "support@fake-mailbox.test"  # the Source filter's value
SUMMIT_SENDER = "noreply@fake-builder.test"  # the Source column's value
SUMMIT_AGENT = "Agent 2 (Summit Homes)"  # config/clients/summit.toml
UNASSIGNED = "---"  # an empty Assignee cell (screen-map row 01)


def summit_title(po: str = "123456/020/01", word: str = "READY") -> str:
    return f"Fake Builder Homes - Lot 1 St No 2 Sample Street - PO: {po} - {word}"


def summit_row(
    note_id: str,
    *,
    title: str | None = None,
    source: str = SUMMIT_SENDER,
    project: str = UNASSIGNED,
    assignee: str = UNASSIGNED,
) -> NotePoolRow:
    return NotePoolRow(
        note_id=note_id,
        subject_note=summit_title() if title is None else title,
        project=project,
        assignee=assignee,
        source=source,
    )


# A fake Summit PO as both readers read it (SPEC.md -> Client 2, PDF
# patterns: the company line on top, "Purchase Order No:", the item row
# between the DESCRIPTION header and the totals). Company names and
# creators may be committed (config/clients/summit.toml); everything else is
# fake.
SUMMIT_COMPANY = "Summit Homes Group"  # creator Compactions
SUMMIT_PO = "123456/020/01"
# A Summit email body: a header table, the PO details table, one line of
# text and a Disclaimer (Joey's live screenshots, 25 Nov 2026; shapes only).
SUMMIT_BODY = (
    "Fake Builder Header\n"
    "Purchase Order\t123456/020/01\n"
    "Fake line of text\n"
    "Disclaimer: fake disclaimer text"
)


def summit_pdf(
    po: str = SUMMIT_PO, company: str = SUMMIT_COMPANY, item: str = "COMPACTION TEST"
) -> bytes:
    return text_pdf(
        [
            company,
            f"Purchase Order No: {po}",
            "Fake Supplier Order To",
            "DESCRIPTION Quantity Unit Price Total",
            item,
            "Sub Total: $99.00",
            "Plus GST: $9.90",
            "Order Total: $108.90",
        ]
    )


def summit_file(po: str = SUMMIT_PO) -> str:
    # The attachment link's file name: the PDF's name, with "_" in the PO
    # (Joey's live screenshots, 25 Nov 2026).
    return f"Fake Order {po.replace('/', '_')}.pdf"


def summit_lookup(
    client_ref: str = "123456",
    *,
    company: str = SUMMIT_COMPANY,
    pln: str = "pln_20001",
    internal_no: str | None = None,
) -> MySysLookup:
    # One project by Client Ref No. under a table company, its Client
    # Internal No. and its tasks (screen-map rows 06, 07, 10).
    return MySysLookup(
        search_rows=(SearchRow(pln=pln, client_ref_no=client_ref, company=company),),
        more_pages=False,
        project_internal_no=client_ref if internal_no is None else internal_no,
        project_tasks=(
            ProjectTask(
                task_no="tsk_300001",
                name="Site Start",
                status="Complete",
                task_creator="Fake Staff One",
            ),
        ),
    )


def summit_note(
    po: str = SUMMIT_PO, *, assignee: str = UNASSIGNED, **kwargs
) -> FakeNote:
    """A Summit Note that PROCEEDs (Summit Homes Group, creator Compactions),
    unless `kwargs` change it."""
    values: dict = {
        "names": (summit_file(po),),
        "pdf": summit_pdf(po),
        "body": SUMMIT_BODY,
        "lookup": summit_lookup(po.split("/")[0]),
    }
    values.update(kwargs)
    return FakeNote(po.split("/")[0], assignee=assignee, **values)


def summit_titled(po: str = SUMMIT_PO, company: str = SUMMIT_COMPANY) -> str:
    return f"{company} - Lot 1 Fake Street Fakeville - PO: {po} - READY"


def install(
    monkeypatch: pytest.MonkeyPatch, fake: FakeMySys, *, booker: bool = True
) -> FakeMySys:
    """Patches the driver's MySys steps (`DRIVER_NAMES`) and, with `booker`,
    the booker's (`BOOKER_DRIVER_NAMES`, `BOOKING_NAMES`) with `fake`'s.
    Every name must exist in its module, so a renamed driver function fails
    here instead of staying silently unpatched."""
    names = DRIVER_NAMES + BOOKER_DRIVER_NAMES if booker else DRIVER_NAMES
    for name in names:
        monkeypatch.setattr(run.driver, name, getattr(fake, name))
    if booker:
        for name in BOOKING_NAMES:
            monkeypatch.setattr(booking, name, getattr(fake, name))
    return fake

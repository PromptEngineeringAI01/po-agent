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

from po_agent.b1.models import MySysLookup, NotePoolRow
from po_agent.core import run
from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys import booking, driver

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

    def open_note_pool(self, guard, page):
        self.calls.append("open_note_pool")
        return "panel"

    def leave_menu(self, guard, page):
        self.calls.append("leave_menu")

    def set_note_pool_filters(self, guard, panel, pool_name):
        # The list reloads by itself after a filter change (screen-map row 27).
        self.calls.append("filters")

    def read_note_pool(self, guard, panel):
        # Page 1 of `pool_pages`, as the footer "Page 1 of N" tells (screen-map
        # row 01); more than one page stops the run (decisions, 5 Nov 2026,
        # silent-skip alert and more pages).
        self.reads += 1
        self.calls.append("read")
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
        return driver.Pdf(file_name=note.names[0], data=PDF)

    def note_body(self, window, file_name):
        # The Note body, one line ending with the file name (screen-map row 02).
        note_id, _ = self._note(window)
        self._call("body", note_id)
        return CLEAN.note.body

    def project_lookup(
        self, guard, page, base_url, username, password, internal_no, site
    ):
        # The real one reloads base_url: the Note window is gone after it
        # (screen-map rows 25, 27).
        (note_id,) = [n for n, v in self.notes.items() if v.internal_no == internal_no]
        self._call("lookup", note_id)
        return self.notes[note_id].lookup

    def return_note(self, guard, window, agent, pool, log, note_id):
        # One Assign with --Select User-- and the pool: "Assignee:" reads the
        # pool (screen-map rows 15, 15b).
        _, note = self._note(window)
        self._call("return", note_id)
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

    def reopen_project(self, guard, page, base_url, username, password, proceed, site):
        # The project window (screen-map row 07).
        self._call("reopen", proceed.note_id)
        return "project"

    def open_task_form(self, guard, page, project):
        self._step("form")  # Create New Task (screen-map row 08)
        return "form"

    def fill_task_form(self, guard, form, po_number, body, file_name, data):
        self._step("fill")  # Compaction Test ticked and filled (screen-map row 09)

    def submit_task(self, guard, form):
        self._step("submit")  # the write (screen-map row 08)
        guard.history.append(("submit_task", "done"))

    def new_task_after_submit(self, form, project, before):
        # One new Compaction Test task on the project (screen-map row 10).
        self._step("new_task")
        return self.task_no

    def check_new_task_row(self, project, task_no, agent):
        self._step("task_row")  # the new task's details row (screen-map row 10)
        return "details"

    def open_task_detail(self, guard, project, details):
        self._step("open_detail")  # opened from the details row (screen-map row 19)

    def check_task_detail(self, page, task_no, po_number, body, agent):
        self._step("detail")  # the task detail screen (screen-map row 19)
        return "detail-window"

    def back_to_project(self, guard, page, window, pln):
        self._step("back")  # "-- Select Task --" (screen-map row 19)

    def check_project_document(
        self, guard, page, pln, task_no, file_name, document_type
    ):
        # The new task's section of the project's Documents tab (screen-map
        # row 19).
        self._step("document")

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

    def link_project(self, guard, page, window, pln, unticked=None):
        # The real one reads Send Email back unticked right before Link to
        # Project and again right before its committing select (`unticked`
        # is told each time), as guard.act records them (decisions, 4 Nov
        # 2026, W4 and W5; screen-map rows 13, 20).
        self._step("link")
        for action in ("link_to_project", "link_select_project"):
            if unticked is not None:
                unticked()
            guard.history.append((action, "done"))

    def log_line_count(self, window):
        self._step("log_count")
        return 0

    def mark_solved(self, guard, window, agent, unticked=None):
        # Send Email read back unticked, then Solved once (decisions, 4 Nov
        # 2026, W4 and W5; screen-map row 14).
        self._step("solved")
        if unticked is not None:
            unticked()
        guard.history.append(("mark_solved", "done"))  # as guard.act records it

    def check_solved_log(self, window, before):
        self._step("solved_log")  # "Status changed: ... to Solved" (screen-map row 14)

    def gone_from_pending(self, guard, page, base_url, username, password, note_id):
        # A Solved Note leaves the Pending list (screen-map row 14).
        self._call("gone", note_id)


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

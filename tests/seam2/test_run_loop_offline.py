"""The Note loop in core/run.py, offline: decide-only (task 3.3) and run
mode, which books (task 4.5).

Not `testsite`: the driver is a fake of MySys, so nothing opens a browser;
the decision engine and both PDF readers run for real on a fake PDF built
by seam 1's `text_pdf` (no committed PDF). The fake keeps each Note's
assignee, so a test can check where every Note ends.

`po-agent run --site test --decide-only` reads the Note Pool once, takes the
eligible Notes oldest first by Note ID, up to `max_notes_per_run`, and for
each: find it (reload, exact ID) -> its assignee is the pool -> take -> 2a ->
attachments -> download -> decide -> back to the pool -> one NOTE line.
Nothing is booked. An error while the agent holds a Note -> one return in a
fresh browser context, then the run stops (exit 1). Values are fake.

`po-agent run --site test` (4.5) runs the same loop, but a PROCEED goes to
the real booker (`book()`, W1-W5) instead of back to the pool. Its MySys
steps (`mysys/driver.py`, `mysys/booking.py`) are faked here too; the real
`Controls.before_write` re-reads the kill switch from the test's config file
and runs the real assignee check over the fake Note Pool search. From the
Submit click on, a Note is never returned to the pool.
"""

import importlib.util
import json
import tempfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.b1.models import MySysLookup, NotePoolRow
from po_agent.core import run
from po_agent.core.config import CONFIG_DIR
from po_agent.core.errors import AccuracyBreach, GuardRefusal, UnexpectedScreen
from po_agent.mysys import booking, driver

_spec = importlib.util.spec_from_file_location(
    "seam1_cases_for_run_loop",
    Path(__file__).parents[1] / "seam1" / "seam1_cases.py",
)
seam1_cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seam1_cases)

POOL = "Agent Pool"
AGENT = "Agent 1 (MySys Only)"
PERSON = "<a person>"
CLEAN = next(case for case in seam1_cases.CASES if case.id == "p1-clean")
FILE = "2600001B_048_1.pdf"
# Both readers read these lines alike (as tests/seam1/test_seam1_real_data.py).
PDF = seam1_cases.text_pdf(
    [line for line in CLEAN.pypdf_text.splitlines() if "(" not in line]
)


@dataclass
class FakeNote:
    """One Note as the fake MySys holds it."""

    internal_no: str
    assignee: str = POOL
    linked: bool = False
    names: tuple[str, ...] = (FILE,)
    lookup: MySysLookup = CLEAN.lookup
    fail_at: str | None = None  # a call name that raises `fail_with`
    fail_with: type[BaseException] = UnexpectedScreen
    person_takes_at: str | None = None  # a call during which a person takes it
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
    pool_pages: int = 1  # pages of the run's filtered Note Pool read
    config_dir: Path | None = None  # the run's config, for `kill_at`
    task_no: str = "tsk_200002"  # the task the fake Submit creates
    current: str | None = None  # the Note last named in a call
    calls: list[str] = field(default_factory=list)
    downloads: list[Path | None] = field(default_factory=list)
    reads: int = 0

    def _note(self, window: str) -> tuple[str, FakeNote]:
        note_id = window.removeprefix("window-")
        return note_id, self.notes[note_id]

    def _call(self, name: str, note_id: str | None = None) -> None:
        self.calls.append(f"{name} {note_id}" if note_id else name)
        if note_id:
            self.current = note_id
        note = self.notes.get(note_id) if note_id else None
        if note and note.person_takes_at == name:
            note.assignee = PERSON
        if note and note.kill_at == name:
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
        if note and note.fail_at == name:
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
        self.calls.append("login")

    def open_note_pool(self, guard, page):
        self.calls.append("open_note_pool")
        return "panel"

    def leave_menu(self, guard, page):
        self.calls.append("leave_menu")

    def set_note_pool_filters(self, guard, panel, pool_name):
        self.calls.append("filters")

    def read_note_pool(self, guard, panel):
        self.reads += 1
        self.calls.append("read")
        return driver.NotePoolList(
            rows=self.rows, total=len(self.rows), pages=self.pool_pages
        )

    def read_agent_notes(self, guard, panel, agent, *, by_agent):
        self.calls.append("agent_notes")
        rows = self.agent_rows
        return driver.NotePoolList(rows=rows, total=len(rows), pages=self.agent_pages)

    def find_note_again(self, guard, page, base_url, username, password, note_id):
        # The real one reloads base_url first: a reload before every Note.
        self._call("find_again", note_id)
        return f"window-{note_id}"

    def read_assignee(self, window):
        note_id, note = self._note(window)
        self._call("assignee", note_id)
        return note.assignee

    def take_note(self, guard, window, agent, log, note_id):
        _, note = self._note(window)
        note.taken += 1
        self._call("take", note_id)
        note.assignee = agent

    def is_unlinked(self, window, log, note_id):
        _, note = self._note(window)
        self._call("2a", note_id)
        return not note.linked

    def attachment_names(self, window):
        note_id, note = self._note(window)
        self._call("names", note_id)
        return note.names

    @contextmanager
    def note_downloads(self, page, folder):
        yield

    def download_pdf(self, guard, page, window):
        note_id, note = self._note(window)
        self._call("download", note_id)
        if len(note.names) != 1 or not note.names[0].lower().endswith(".pdf"):
            return None
        return driver.Pdf(file_name=note.names[0], data=PDF)

    def note_body(self, window, file_name):
        note_id, _ = self._note(window)
        self._call("body", note_id)
        return CLEAN.note.body

    def project_lookup(
        self, guard, page, base_url, username, password, internal_no, site
    ):
        # The real one reloads base_url: the Note window is gone after it.
        (note_id,) = [n for n, v in self.notes.items() if v.internal_no == internal_no]
        self._call("lookup", note_id)
        return self.notes[note_id].lookup

    def return_note(self, guard, window, agent, pool, log, note_id):
        _, note = self._note(window)
        self._call("return", note_id)
        if self.fail_return:
            raise UnexpectedScreen("fake return failure", note_id=note_id)
        note.assignee = pool

    # --- the booker's MySys steps (4.5), named after the Note in hand ------------

    def _step(self, name: str) -> None:
        self._call(name, self.current)

    def search_note(self, guard, page, base_url, username, password, note_id):
        # The assignee check before W1 and W4 (controls.assignee_check).
        self._call("check", note_id)
        note = self.notes[note_id]
        rows = (row(note_id, note.internal_no, assignee=note.assignee),)
        return "panel", driver.NotePoolList(rows=rows, total=1, pages=1)

    def reopen_project(self, guard, page, base_url, username, password, proceed, site):
        self._call("reopen", proceed.note_id)
        return "project"

    def open_task_form(self, guard, page, project):
        self._step("form")
        return "form"

    def fill_task_form(self, guard, form, po_number, body, file_name, data):
        self._step("fill")

    def submit_task(self, guard, form):
        self._step("submit")
        guard.history.append(("submit_task", "done"))

    def new_task_after_submit(self, form, project, before):
        self._step("new_task")
        return self.task_no

    def check_new_task_row(self, project, task_no, agent):
        self._step("task_row")
        return "details"

    def open_task_detail(self, guard, project, details):
        self._step("open_detail")

    def check_task_detail(self, page, task_no, po_number, body, agent):
        self._step("detail")
        return "detail-window"

    def back_to_project(self, guard, page, window, pln):
        self._step("back")

    def check_project_document(
        self, guard, page, pln, task_no, file_name, document_type
    ):
        self._step("document")

    def project_window(self, page, pln):
        self._step("project_window")
        return "project"

    def open_hold(self, guard, page, project, task_no):
        self._step("open_hold")
        return "dialog"

    def fill_hold(self, guard, dialog):
        self._step("fill_hold")

    def confirm_hold(self, guard, page, dialog):
        self._step("confirm_hold")
        guard.history.append(("confirm_hold", "done"))

    def check_on_hold(self, project, task_no):
        self._step("on_hold")

    def link_project(self, guard, page, window, pln, unticked=None):
        # The real one reads Send Email back unticked right before Link to
        # Project and again right before its committing select (`unticked`
        # is told each time), as guard.act records them.
        self._step("link")
        for action in ("link_to_project", "link_select_project"):
            if unticked is not None:
                unticked()
            guard.history.append((action, "done"))

    def log_line_count(self, window):
        self._step("log_count")
        return 0

    def mark_solved(self, guard, window, agent, unticked=None):
        self._step("solved")
        if unticked is not None:
            unticked()
        guard.history.append(("mark_solved", "done"))  # as guard.act records it

    def check_solved_log(self, window, before):
        self._step("solved_log")

    def gone_from_pending(self, guard, page, base_url, username, password, note_id):
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
    return NotePoolRow(
        note_id=note_id,
        subject_note=f"Please find attached file {internal_no}_048_1.pdf",
        project="---",
        assignee=assignee,
    )


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Fake secrets, temp and logs under tmp_path, max_notes_per_run = 3."""
    monkeypatch.setenv("PO_AGENT_MYSYS_TEST_USERNAME", "fake-user")
    monkeypatch.setenv("PO_AGENT_MYSYS_TEST_PASSWORD", "fake-password")
    previous = keyring.get_keyring()
    keyring.set_keyring(NullKeyring())
    temp = tmp_path / "temp"
    temp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp))
    monkeypatch.setattr(cli, "LOGS_DIR", tmp_path / "logs")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    toml = (CONFIG_DIR / "test.toml").read_text("utf-8")
    assert "max_notes_per_run = 10" in toml
    (config_dir / "test.toml").write_text(
        toml.replace("max_notes_per_run = 10", "max_notes_per_run = 3"), "utf-8"
    )
    monkeypatch.setattr(cli, "CONFIG_DIR", config_dir)
    yield monkeypatch
    keyring.set_keyring(previous)


@pytest.fixture
def mysys(env, tmp_path):
    def install(notes: dict[str, FakeNote], rows=None, **kwargs) -> FakeMySys:
        rows = rows or tuple(row(n, note.internal_no) for n, note in notes.items())
        fake = FakeMySys(
            notes=notes,
            rows=tuple(rows),
            config_dir=tmp_path / "config",
            logs_dir=tmp_path / "logs",
            **kwargs,
        )
        for name in DRIVER_NAMES + BOOKER_DRIVER_NAMES:
            # raising=False: note_body moves into the driver in 3.3.
            env.setattr(run.driver, name, getattr(fake, name), raising=False)
        for name in BOOKING_NAMES:
            env.setattr(booking, name, getattr(fake, name))
        return fake

    return install


def decide_only(*extra: str) -> int:
    return cli.main(["run", "--site", "test", "--decide-only", *extra])


def output(capsys) -> list[str]:
    captured = capsys.readouterr()
    assert captured.err == ""
    return captured.out.splitlines()


def notes_of(lines: list[str]) -> list[dict]:
    return [json.loads(x.removeprefix("NOTE  ")) for x in lines if x.startswith("NOTE")]


def alerts_of(lines: list[str]) -> list[tuple[str, dict]]:
    found = []
    for line in lines:
        if line.startswith("ALERT "):
            kind, _, body = line.removeprefix("ALERT ").partition(" ")
            found.append((kind, json.loads(body)))
    return found


def summary_of(lines: list[str]) -> dict:
    assert lines[-1].startswith("RUN_SUMMARY ")
    return json.loads(lines[-1].removeprefix("RUN_SUMMARY "))


def opened(fake: FakeMySys) -> list[str]:
    """The Note IDs found and opened, in order, each once (a Note is found
    again before it goes back)."""
    found = [c.split()[1] for c in fake.calls if c.startswith("find_again ")]
    return list(dict.fromkeys(found))


# --- the loop ----------------------------------------------------------------


def test_eligible_notes_go_oldest_first_up_to_the_cap_from_one_list_read(mysys, capsys):
    # List order is newest first; 99998 is the oldest (a number, not text).
    fake = mysys(
        {
            "300010": FakeNote("2600010B", names=()),
            "300002": FakeNote("2600002B", names=()),
            "300001": FakeNote("2600001B", names=()),
            "99998": FakeNote("2600998B", names=()),
        },
        rows=(
            row("300010", "2600010B"),
            row("300007", "2600007B", assignee=PERSON),  # not eligible
            row("300002", "2600002B"),
            row("300001", "2600001B"),
            row("99998", "2600998B"),
        ),
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 0
    assert fake.reads == 1
    assert opened(fake) == ["99998", "300001", "300002"]
    # Past the cap and not eligible: never opened, never taken.
    assert not [c for c in fake.calls if "300010" in c or "300007" in c]
    assert fake.notes["300010"].taken == 0
    # Each processed Note taken once and back in the pool.
    assert Counter(n for n, v in fake.notes.items() if v.taken) == Counter(
        ["99998", "300001", "300002"]
    )
    assert all(v.taken <= 1 for v in fake.notes.values())
    assert all(v.assignee == POOL for v in fake.notes.values())
    assert [n["note_id"] for n in notes_of(lines)] == ["99998", "300001", "300002"]
    summary = summary_of(lines)
    assert summary["mode"] == "decide-only"
    assert (summary["seen"], summary["eligible"]) == (5, 4)
    assert (summary["skipped"], summary["booked"], summary["exit_code"]) == (3, 0, 0)


def test_one_note_line_per_note_and_nothing_booked(mysys, capsys):
    fake = mysys(
        {
            "300001": FakeNote("2600001B"),
            "300002": FakeNote("2600002B", names=()),
            "300003": FakeNote("2600003B", linked=True),
        }
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 0
    zero = {"field": None, "task_id": None, "tokens_in": 0, "tokens_out": 0}
    assert notes_of(lines) == [
        {
            "note_id": "300001",
            "outcome": "skipped",
            "reason": "DECIDE_ONLY",
            "po_number": "2600001B/048",
            "pln": "pln_10001",
            "cost_aud": 0.0,
            **zero,
        },
        {
            "note_id": "300002",
            "outcome": "skipped",
            "reason": "NO_PDF",
            "po_number": "2600002B/048",
            "pln": None,
            "cost_aud": 0.0,
            **zero,
        },
        {
            "note_id": "300003",
            "outcome": "skipped",
            "reason": "NOTE_ALREADY_LINKED",
            "po_number": "2600003B/048",
            "pln": None,
            "cost_aud": 0.0,
            **zero,
        },
    ]
    # Every Note is found again, its Assignee read, before it goes back (a
    # person may have taken it meanwhile). A Note skipped before the project
    # read has no download or project read it doesn't need.
    per_note = {
        n: [c.split()[0] for c in fake.calls if c.endswith(f" {n}")] for n in fake.notes
    }
    assert per_note == {
        "300001": [
            "find_again",
            "assignee",
            "take",
            "2a",
            "names",
            "download",
            "body",
            "lookup",
            "find_again",
            "assignee",
            "return",
        ],
        "300002": [
            "find_again",
            "assignee",
            "take",
            "2a",
            "names",
            "download",
            "find_again",
            "assignee",
            "return",
        ],
        "300003": [
            "find_again",
            "assignee",
            "take",
            "2a",
            "find_again",
            "assignee",
            "return",
        ],
    }
    assert all(v.assignee == POOL for v in fake.notes.values())
    summary = summary_of(lines)
    assert (summary["skipped"], summary["booked"], summary["partial"]) == (3, 0, 0)
    assert (summary["tokens_in"], summary["tokens_out"], summary["cost_aud"]) == (
        0,
        0,
        0.0,
    )
    # The run's own download folder (D2), gone when the run ends.
    (folder,) = {d for d in fake.downloads}
    assert folder.name == f"po-agent-dl-{summary['run_id']}"
    assert not folder.exists()


def test_a_note_a_person_holds_is_never_taken(mysys, capsys):
    fake = mysys({"300001": FakeNote("2600001B", assignee=PERSON)})

    code = decide_only()

    lines = output(capsys)
    assert code == 0
    assert fake.notes["300001"].taken == 0
    assert fake.notes["300001"].assignee == PERSON
    assert not [c for c in fake.calls if c.startswith(("take", "return"))]
    (note,) = notes_of(lines)
    assert (note["outcome"], note["reason"]) == ("untouched", "NOTE_TAKEN")
    assert summary_of(lines)["skipped"] == 0


@pytest.mark.parametrize("during", ["lookup", "2a"])
def test_a_note_a_person_takes_mid_run_is_not_returned(mysys, capsys, during):
    fake = mysys(
        {
            "300001": FakeNote("2600001B", person_takes_at=during),
            "300002": FakeNote("2600002B", names=()),
        }
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 0
    assert "return 300001" not in fake.calls
    assert fake.notes["300001"].assignee == PERSON
    assert fake.notes["300002"].assignee == POOL  # the run goes on
    first, _ = notes_of(lines)
    assert (first["note_id"], first["outcome"], first["reason"]) == (
        "300001",
        "untouched",
        "NOTE_TAKEN",
    )


# --- stop on the first failure ---------------------------------------------------

WRONG_PROJECT = CLEAN.lookup.model_copy(update={"project_internal_no": "2600009B"})


@pytest.mark.parametrize(
    "failing",
    [
        FakeNote("2600001B", fail_at="lookup"),  # UnexpectedScreen
        FakeNote("2600001B", lookup=WRONG_PROJECT),  # Skip(UNEXPECTED_SCREEN)
    ],
    ids=["unexpected-screen", "skip-unexpected-screen"],
)
def test_an_unexpected_screen_returns_the_note_in_a_fresh_context_then_stops(
    mysys, capsys, failing
):
    fake = mysys({"300001": failing, "300002": FakeNote("2600002B", names=())})

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert "300002" not in opened(fake)  # the run stopped
    # The old browser closed, then one return through the normal path.
    after = fake.calls[fake.calls.index("closed") :]
    assert after == [
        "closed",
        "open_browser",
        "find_again 300001",
        "assignee 300001",
        "return 300001",
        "closed",
    ]
    assert fake.notes["300001"].assignee == POOL
    assert notes_of(lines) == []
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")
    summary = summary_of(lines)
    assert (summary["exit_code"], summary["booked"]) == (1, 0)


def test_a_failed_return_leaves_the_note_with_the_agent_and_the_alert_says_so(
    mysys, capsys
):
    fake = mysys({"300001": FakeNote("2600001B", fail_at="lookup")}, fail_return=True)

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert [c for c in fake.calls if c.startswith("return")] == ["return 300001"]
    assert fake.notes["300001"].assignee == AGENT
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")
    assert "not returned to the pool" in alert["detail"]
    assert summary_of(lines)["exit_code"] == 1


def test_an_error_before_the_note_is_taken_stops_without_a_return(mysys, capsys):
    fake = mysys({"300001": FakeNote("2600001B", fail_at="find_again")})

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert fake.calls.count("open_browser") == 1
    assert fake.notes["300001"].taken == 0
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")


def test_any_other_error_after_the_take_returns_the_note_and_names_it(mysys, capsys):
    fake = mysys(
        {"300001": FakeNote("2600001B", fail_at="download", fail_with=RuntimeError)}
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert fake.notes["300001"].assignee == POOL
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")


def test_ctrl_c_after_the_take_names_the_note_as_not_returned(mysys, capsys):
    # Joey stopping a watched laptop run: no return attempt, but the ALERT
    # says which Note stays with the agent.
    fake = mysys(
        {
            "300001": FakeNote(
                "2600001B", fail_at="download", fail_with=KeyboardInterrupt
            )
        }
    )

    code = decide_only()

    lines = output(capsys)
    assert code == 1
    assert fake.calls.count("open_browser") == 1
    assert fake.notes["300001"].assignee == AGENT
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"]) == ("UNEXPECTED_SCREEN", "300001")
    assert "not returned to the pool" in alert["detail"]


# --- the detailed log ------------------------------------------------------------


def test_detailed_log_has_the_skips_and_one_traceback_per_error(
    mysys, capsys, tmp_path
):
    mysys(
        {
            "300001": FakeNote("2600001B", names=()),
            # Fails at the download: the fake PDF is 2600001B's, so this
            # Note would skip PO_MISMATCH before any project lookup.
            "300002": FakeNote("2600002B", fail_at="download"),
        }
    )

    code = decide_only("--detailed-log")

    run_id = summary_of(output(capsys))["run_id"]
    assert code == 1
    log = tmp_path / "logs" / f"{run_id}.jsonl"
    events = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    named = [
        (e["event"], e["note_id"], e.get("reason") or e.get("type")) for e in events
    ]
    assert ("skip", "300001", "NO_PDF") in named
    assert ("error", "300002", "UnexpectedScreen") in named
    assert [e["event"] for e in events].count("traceback") == 1


def test_without_detailed_log_nothing_is_written_to_logs(mysys, capsys, tmp_path):
    mysys({"300001": FakeNote("2600001B", fail_at="lookup")})

    assert decide_only() == 1
    output(capsys)
    assert not (tmp_path / "logs").exists()


# --- run mode: book end to end (4.5) ---------------------------------------------

W1_TO_W5 = [
    "check",  # W1's assignee check (D7)
    "reopen",
    "form",
    "fill",
    "submit",  # the partial-write line
    "new_task",
    "task_row",
    "open_detail",
    "detail",
    "back",
    "document",
    "project_window",
    "open_hold",
    "fill_hold",
    "confirm_hold",
    "on_hold",
    "check",  # W4's assignee check (D7)
    "find_again",
    "link",
    "log_count",
    "solved",
    "solved_log",
    "gone",
]


def book_run(*extra: str) -> int:
    return cli.main(["run", "--site", "test", *extra])


def calls_for(fake: FakeMySys, note_id: str) -> list[str]:
    return [c.split()[0] for c in fake.calls if c.endswith(f" {note_id}")]


def test_run_books_a_proceed_w1_to_w5_and_returns_a_skip(mysys, capsys):
    fake = mysys(
        {
            "300001": FakeNote("2600001B"),  # PROCEED
            "300002": FakeNote("2600002B", names=()),  # NO_PDF
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 0
    assert calls_for(fake, "300001") == [
        "find_again",
        "assignee",
        "take",
        "2a",
        "names",
        "download",
        "body",
        "lookup",
        *W1_TO_W5,
    ]
    # Booked: never returned (the Note is linked and Solved, with the agent).
    assert "return 300001" not in fake.calls
    assert fake.notes["300001"].assignee == AGENT
    assert fake.notes["300002"].assignee == POOL
    assert "context_closed" not in fake.calls
    zero = {"field": None, "tokens_in": 0, "tokens_out": 0, "cost_aud": 0.0}
    booked, skipped = notes_of(lines)
    assert booked == {
        "note_id": "300001",
        "outcome": "booked",
        "reason": None,
        "po_number": "2600001B/048",
        "pln": "pln_10001",
        "task_id": "tsk_200002",
        **zero,
    }
    assert (skipped["note_id"], skipped["outcome"], skipped["reason"]) == (
        "300002",
        "skipped",
        "NO_PDF",
    )
    assert alerts_of(lines) == []
    summary = summary_of(lines)
    assert summary["mode"] == "run"
    assert (summary["booked"], summary["skipped"], summary["partial"]) == (1, 1, 0)
    assert summary["exit_code"] == 0


BOOKER_WRITES = (
    "submit_task",
    "confirm_hold",
    "link_to_project",
    "link_select_project",
    "mark_solved",
)


@pytest.mark.parametrize("at", ["check", "link", "solved"])
def test_a_run_log_that_cant_be_written_mid_booking_doesnt_stop_it(mysys, capsys, at):
    # 5.2 review: the booker's run-log writes (W1/W4 checks, W4/W5 read-back
    # events, step flushes) never turn a booking into a partial write.
    fake = mysys({"300001": FakeNote("2600001B")}, break_log_at=at)

    code = book_run("--detailed-log")

    lines = output(capsys)
    assert "gone 300001" in fake.calls
    (booked,) = notes_of(lines)
    assert (booked["outcome"], booked["task_id"]) == ("booked", "tsk_200002")
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"], code) == (1, 0, 0)


def test_the_detailed_log_has_send_email_unticked_after_w4s_check_before_w4_and_w5(
    mysys, capsys, tmp_path
):
    # 5.2, D7: the booker's assignee checks (W1, W4) and its Send Email
    # read-backs (W4's select, W5's Solved) are in the detailed log, in order.
    mysys({"300001": FakeNote("2600001B")})

    assert book_run("--detailed-log") == 0

    run_id = summary_of(output(capsys))["run_id"]
    log = tmp_path / "logs" / f"{run_id}.jsonl"
    events = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    named = [
        (e["event"], e["step"], e.get("action"))
        for e in events
        if e["note_id"] == "300001"
        and (
            e["event"] in ("assignee_check", "email_notification_unticked")
            or e.get("action") in BOOKER_WRITES
        )
    ]
    # Each guard action carries its own W step (the safe trace, SPEC.md).
    assert named == [
        ("assignee_check", "2", None),
        ("assignee_check", "W1", None),
        ("guard_action", "W2", "submit_task"),
        ("guard_action", "W3", "confirm_hold"),
        ("assignee_check", "W4", None),
        ("email_notification_unticked", "W4", None),
        ("guard_action", "W4", "link_to_project"),
        ("email_notification_unticked", "W4", None),
        ("guard_action", "W4", "link_select_project"),
        ("email_notification_unticked", "W5", None),
        ("guard_action", "W5", "mark_solved"),
    ]
    assert all(
        e["ok"]
        for e in events
        if e["event"] in ("assignee_check", "email_notification_unticked")
    )


def test_a_note_taken_at_the_w1_check_is_untouched_and_the_next_runs_in_a_new_context(
    mysys, capsys
):
    fake = mysys(
        {
            # A person takes it while the project is read (step 10).
            "300001": FakeNote("2600001B", person_takes_at="lookup"),
            "300002": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 0
    # Nothing written for 300001, and it stays with the person.
    assert calls_for(fake, "300001")[-2:] == ["lookup", "check"]
    assert "return 300001" not in fake.calls
    assert fake.notes["300001"].assignee == PERSON
    # Its browser context closed, then a fresh one for the next Note. The
    # sync API holds one browser per thread, so the old one closes first.
    checked = fake.calls.index("check 300001")
    assert fake.calls[checked + 1 : checked + 4] == [
        "context_closed",
        "closed",
        "open_browser",
    ]
    assert fake.calls.index("find_again 300002") > checked + 3
    assert fake.notes["300002"].assignee == POOL
    first, second = notes_of(lines)
    assert (first["note_id"], first["outcome"], first["reason"]) == (
        "300001",
        "untouched",
        "NOTE_TAKEN",
    )
    assert (second["note_id"], second["reason"]) == ("300002", "NO_PDF")
    assert alerts_of(lines) == []
    summary = summary_of(lines)
    assert (summary["booked"], summary["skipped"], summary["exit_code"]) == (0, 1, 0)


@pytest.mark.parametrize(
    ("kill_at", "closed_by_booker"),
    [("lookup", False), ("fill", True)],
    ids=["before-w1", "before-w2"],
)
def test_a_kill_switch_at_w1_or_w2_returns_the_note_in_a_fresh_context_and_exits_0(
    mysys, capsys, kill_at, closed_by_booker
):
    fake = mysys(
        {
            "300001": FakeNote("2600001B", kill_at=kill_at),
            "300002": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 0
    assert "submit 300001" not in fake.calls
    assert ("context_closed" in fake.calls) is closed_by_booker
    after = fake.calls[fake.calls.index("closed") :]
    assert after == [
        "closed",
        "open_browser",
        "find_again 300001",
        "assignee 300001",
        "return 300001",
        "closed",
    ]
    assert fake.notes["300001"].assignee == POOL
    assert "300002" not in opened(fake)
    assert "INFO  kill switch on: run stopped" in lines
    assert alerts_of(lines) == []
    assert notes_of(lines) == []
    assert summary_of(lines)["exit_code"] == 0


def test_write_not_started_returns_the_note_in_a_fresh_context_and_stops(mysys, capsys):
    # The Create New Task form not filled as read back (W1): nothing submitted.
    fake = mysys(
        {
            "300001": FakeNote("2600001B", fail_at="fill"),
            "300002": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 1
    assert "submit 300001" not in fake.calls
    after = fake.calls[fake.calls.index("context_closed") :]
    assert after == [
        "context_closed",
        "closed",
        "open_browser",
        "find_again 300001",
        "assignee 300001",
        "return 300001",
        "closed",
    ]
    assert fake.notes["300001"].assignee == POOL
    assert "300002" not in opened(fake)
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"], alert["step"]) == (
        "UNEXPECTED_SCREEN",
        "300001",
        "W1",
    )
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"], summary["exit_code"]) == (0, 0, 1)


AFTER_SUBMIT = [
    # (FakeNote changes, ALERT kind, step, exit code)
    ({"fail_at": "submit", "fail_with": RuntimeError}, "PARTIAL_WRITE", "W2", 1),
    ({"fail_at": "new_task"}, "PARTIAL_WRITE", "W2", 1),  # UnexpectedScreen
    ({"fail_at": "detail", "fail_with": AccuracyBreach}, "ACCURACY_BREACH", "W2", 3),
    ({"kill_at": "document"}, "PARTIAL_WRITE", "W3", 1),  # the kill switch at W3
    ({"fail_at": "confirm_hold", "fail_with": RuntimeError}, "PARTIAL_WRITE", "W3", 1),
    ({"person_takes_at": "on_hold"}, "PARTIAL_WRITE", "W4", 1),  # taken at W4
    # A Note someone linked meanwhile: no Link to Project to press (4.4).
    ({"fail_at": "link", "fail_with": GuardRefusal}, "GUARD_REFUSAL", "W4", 1),
    ({"fail_at": "gone"}, "PARTIAL_WRITE", "W5", 1),  # UnexpectedScreen
]


@pytest.mark.parametrize(
    ("changes", "kind", "step", "exit_code"),
    AFTER_SUBMIT,
    ids=[
        "submit-click-fails",
        "unexpected-screen-after-submit",
        "accuracy-breach-w2",
        "kill-switch-w3",
        "hold-confirm-fails",
        "note-taken-w4",
        "guard-refusal-w4",
        "not-gone-w5",
    ],
)
def test_from_the_submit_click_on_the_note_is_never_returned_and_the_run_stops(
    mysys, capsys, changes, kind, step, exit_code
):
    fake = mysys(
        {
            "300001": FakeNote("2600001B", **changes),
            "300002": FakeNote("2600002B", names=()),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == exit_code
    assert "submit 300001" in fake.calls
    # No return attempted: no fresh browser, no Assign back to the pool.
    assert fake.calls.count("open_browser") == 1
    assert not [c for c in fake.calls if c.startswith("return")]
    assert fake.notes["300001"].assignee in (AGENT, PERSON)
    assert "300002" not in opened(fake)  # the run stopped
    ((alert_kind, alert),) = alerts_of(lines)
    assert (alert_kind, alert["note_id"], alert["step"]) == (kind, "300001", step)
    assert notes_of(lines) == []
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"]) == (0, 1)
    assert summary["exit_code"] == exit_code


# --- run mode: what the run knows about Submit, not the last exception (4.5 review)


def test_a_run_log_that_fails_after_w5_never_returns_the_booked_note(mysys, capsys):
    # --detailed-log, and the log can't be written once the Note is Solved.
    fake = mysys({"300001": FakeNote("2600001B")}, break_log_at="gone")

    code = book_run("--detailed-log")

    lines = output(capsys)
    assert "gone 300001" in fake.calls
    assert not [c for c in fake.calls if c.startswith("return")]
    assert fake.calls.count("open_browser") == 1
    (booked,) = notes_of(lines)
    assert (booked["outcome"], booked["task_id"]) == ("booked", "tsk_200002")
    summary = summary_of(lines)
    assert (summary["booked"], summary["partial"], code) == (1, 0, 0)


def test_a_failed_browser_close_after_submit_keeps_the_partial_write(mysys, capsys):
    # The Hold confirm fails (W3), then closing the browser fails too.
    fake = mysys(
        {
            "300001": FakeNote(
                "2600001B", fail_at="confirm_hold", fail_with=RuntimeError
            )
        },
        close_fails=True,
    )

    code = book_run()

    lines = output(capsys)
    assert code == 1
    assert not [c for c in fake.calls if c.startswith("return")]
    assert fake.calls.count("open_browser") == 1
    ((kind, alert),) = alerts_of(lines)
    assert (kind, alert["note_id"], alert["step"]) == ("PARTIAL_WRITE", "300001", "W3")
    assert summary_of(lines)["partial"] == 1


# --- 7.2: a silent skip can't happen; more pages alerts (decisions, 5 Nov 2026) ---


def test_when_every_eligible_note_would_be_unexpected_screen_the_first_alerts(
    mysys, capsys
):
    # The run stops on the first UNEXPECTED_SCREEN, so a MySys screen change
    # can't skip every Note quietly: one ALERT, exit 1, the next Note untouched.
    fake = mysys(
        {
            "300001": FakeNote("2600001B", fail_at="download"),
            "300002": FakeNote("2600002B", fail_at="download"),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 1
    assert opened(fake) == ["300001"]
    assert [(kind, alert["note_id"]) for kind, alert in alerts_of(lines)] == [
        ("UNEXPECTED_SCREEN", "300001")
    ]
    assert summary_of(lines)["exit_code"] == 1


def test_one_booked_then_one_unexpected_screen_still_alerts(mysys, capsys):
    fake = mysys(
        {
            "300001": FakeNote("2600001B"),  # PROCEED: booked
            "300002": FakeNote("2600002B", fail_at="download"),
        }
    )

    code = book_run()

    lines = output(capsys)
    assert code == 1
    assert [n["outcome"] for n in notes_of(lines)] == ["booked"]
    assert [(kind, alert["note_id"]) for kind, alert in alerts_of(lines)] == [
        ("UNEXPECTED_SCREEN", "300002")
    ]
    assert fake.notes["300002"].assignee == POOL
    summary = summary_of(lines)
    assert (summary["booked"], summary["exit_code"]) == (1, 1)


@pytest.mark.parametrize("command", [book_run, decide_only])
def test_more_pages_in_the_eligible_read_alerts_before_any_note(mysys, capsys, command):
    fake = mysys({"300001": FakeNote("2600001B")}, pool_pages=2)

    code = command()

    lines = output(capsys)
    assert code == 1
    assert opened(fake) == []
    assert not [c for c in fake.calls if c.startswith("take")]
    assert [kind for kind, _ in alerts_of(lines)] == ["MORE_PAGES"]
    assert notes_of(lines) == []
    summary = summary_of(lines)
    assert (summary["seen"], summary["eligible"], summary["exit_code"]) == (1, 1, 1)

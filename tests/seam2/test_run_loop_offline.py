"""The decide-only Note loop in core/run.py (task 3.3), offline.

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
"""

import importlib.util
import json
import tempfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import keyring
import pytest
from keyring.backends.null import Keyring as NullKeyring

from po_agent import cli
from po_agent.b1.models import MySysLookup, NotePoolRow
from po_agent.core import run
from po_agent.core.config import CONFIG_DIR
from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys import driver

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
    taken: int = 0


@dataclass
class FakeMySys:
    notes: dict[str, FakeNote]
    rows: tuple[NotePoolRow, ...]
    fail_return: bool = False
    calls: list[str] = field(default_factory=list)
    downloads: list[Path | None] = field(default_factory=list)
    reads: int = 0

    def _note(self, window: str) -> tuple[str, FakeNote]:
        note_id = window.removeprefix("window-")
        return note_id, self.notes[note_id]

    def _call(self, name: str, note_id: str | None = None) -> None:
        self.calls.append(f"{name} {note_id}" if note_id else name)
        note = self.notes.get(note_id) if note_id else None
        if note and note.person_takes_at == name:
            note.assignee = PERSON
        if note and note.fail_at == name:
            if note.fail_with is UnexpectedScreen:
                raise UnexpectedScreen("fake failure", note_id=note_id)
            raise note.fail_with("fake failure")

    @contextmanager
    def open_browser(self, *, headed, slow_mo, downloads=None):
        self.calls.append("open_browser")
        self.downloads.append(downloads)
        try:
            yield "page"
        finally:
            self.calls.append("closed")

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
        return driver.NotePoolList(rows=self.rows, total=len(self.rows), pages=1)

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


DRIVER_NAMES = (
    "open_browser",
    "go_home",
    "login",
    "open_note_pool",
    "leave_menu",
    "set_note_pool_filters",
    "read_note_pool",
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
def mysys(env):
    def install(notes: dict[str, FakeNote], rows=None, **kwargs) -> FakeMySys:
        rows = rows or tuple(row(n, note.internal_no) for n, note in notes.items())
        fake = FakeMySys(notes=notes, rows=tuple(rows), **kwargs)
        for name in DRIVER_NAMES:
            # raising=False: note_body moves into the driver in 3.3.
            env.setattr(run.driver, name, getattr(fake, name), raising=False)
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
    """The Note IDs found and opened, in order."""
    return [c.split()[1] for c in fake.calls if c.startswith("find_again ")]


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

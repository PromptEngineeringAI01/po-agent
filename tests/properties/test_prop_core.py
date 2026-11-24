"""Properties of the pure helpers outside b1/: the run order, the run window
and cap, the error identifiers, the Note search's exact row and the PR risk
level. The clock is faked; nothing opens a browser.
"""

import importlib.util
import string
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from b1_worlds import note_ids
from hypothesis import assume, given
from hypothesis import strategies as st

from po_agent.b1.models import NotePoolRow
from po_agent.core import controls, errors
from po_agent.core.config import RunWindow, load_config
from po_agent.core.run import EligibleNote, newest_first
from po_agent.mysys.driver import NotePoolList, exact_row

ROOT = Path(__file__).resolve().parents[2]


def _risk():
    # scripts/ isn't a package, so load the file directly (as test_risk.py).
    spec = importlib.util.spec_from_file_location("risk", ROOT / "scripts" / "risk.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


risk = _risk()

# E1: newest first (SPEC -> Note Pool -> Order; decisions, 10 Nov 2026)

NOTES = st.lists(note_ids, unique=True, max_size=12).map(
    lambda ids: [EligibleNote(note_id=i, internal_no="9000001A") for i in ids]
)
CAPS = st.integers(0, 15)


@given(NOTES, CAPS)
def test_newest_first_is_by_note_id_as_a_number_at_most_cap(notes, cap):
    ordered = newest_first(notes, cap)
    numbers = [int(note.note_id) for note in ordered]
    assert numbers == sorted(numbers, reverse=True)
    assert len(ordered) == min(cap, len(notes))
    assert set(ordered) <= set(notes)
    # Only the newest are kept: nothing left out is newer than what's kept.
    left = {int(n.note_id) for n in notes} - set(numbers)
    assert not numbers or not left or max(left) < min(numbers)


@given(NOTES, CAPS, CAPS)
def test_a_smaller_cap_keeps_a_prefix_of_a_larger_one(notes, small, large):
    small, large = sorted((small, large))
    assert newest_first(notes, large)[:small] == newest_first(notes, small)


@given(NOTES, CAPS, st.randoms())
def test_the_list_order_never_changes_the_run_order(notes, cap, random):
    shuffled = list(notes)
    random.shuffle(shuffled)
    assert newest_first(shuffled, cap) == newest_first(notes, cap)


# E2: the run window (SPEC -> Run controls: Mon-Fri, start <= local < end)


@st.composite
def windows(draw):
    start = draw(st.times(max_value=time(22, 0)))
    end = draw(st.times(min_value=start)).replace(microsecond=0)
    assume(start < end)
    return RunWindow(days="Mon-Fri", start=start, end=end, tz="Australia/Perth")


PERTH = ZoneInfo("Australia/Perth")
DAYS = st.dates(min_value=date(2026, 1, 1), max_value=date(2030, 12, 31))


@given(windows(), DAYS, st.times())
def test_never_in_the_window_at_a_weekend(window, day, at):
    assume(day.weekday() >= 5)
    assert not controls.in_window(window, datetime.combine(day, at, PERTH))


@given(windows(), DAYS)
def test_the_window_starts_at_start_and_ends_before_end(window, day):
    assume(day.weekday() < 5)
    assert controls.in_window(window, datetime.combine(day, window.start, PERTH))
    assert not controls.in_window(window, datetime.combine(day, window.end, PERTH))


@given(
    windows(),
    st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2030, 1, 1)),
    st.sampled_from(["UTC", "Australia/Sydney", "America/New_York", "Asia/Kolkata"]),
)
def test_the_same_instant_in_any_time_zone_gives_the_same_answer(window, naive, zone):
    at = naive.replace(tzinfo=UTC)
    elsewhere = at.astimezone(ZoneInfo(zone))
    assert controls.in_window(window, at) == controls.in_window(window, elsewhere)


# E4: the run cap, with a fake clock

CONFIG = load_config("test")
STARTED = datetime(2026, 11, 24, 1, 0, tzinfo=UTC)


def cap_reached(done: int, minutes: float) -> bool:
    with mock.patch.object(
        controls, "now", return_value=STARTED + timedelta(minutes=minutes)
    ):
        return controls.cap_reached(CONFIG, STARTED, done)


@given(st.integers(0, 30), st.floats(0, 120), st.integers(0, 5), st.floats(0, 30))
def test_more_notes_or_more_time_never_lifts_the_cap(done, minutes, more, later):
    if cap_reached(done, minutes):
        assert cap_reached(done + more, minutes + later)


@given(st.integers(0, 30), st.floats(0, 120))
def test_the_cap_holds_from_max_notes_or_max_minutes_on(done, minutes):
    """SPEC -> run cap: at most max_notes_per_run Notes, max_run_minutes."""
    under = done < CONFIG.max_notes_per_run and minutes < CONFIG.max_run_minutes
    assert cap_reached(done, minutes) is not under


# E3: identifiers in errors (SPEC -> Code style: identifiers only, never
# page text)


@given(st.text(max_size=80) | st.none())
def test_an_identifier_is_kept_or_redacted_never_changed(value):
    result = errors.identifier(value)
    assert result in (None, value, errors.REDACTED)
    assert (result is None) == (value is None)
    assert errors.identifier(result) == result


@given(st.text(max_size=80))
def test_an_identifier_never_carries_spaces_or_page_punctuation(value):
    result = errors.identifier(value)
    if result != errors.REDACTED:
        allowed = set(string.ascii_letters + string.digits + "_./-")
        assert set(result) <= allowed and 1 <= len(result) <= 64


# E5: finding a Note again (SPEC -> Note Pool: the row whose ID equals it)


@given(note_ids, st.lists(note_ids, max_size=6), st.integers(0, 2))
def test_exact_row_is_the_one_row_whose_id_equals_the_note_id(note_id, others, copies):
    """The search is a substring filter: 123 also lists 1234."""
    neighbours = [n for n in others + [note_id + "2", "1" + note_id] if n != note_id]
    rows = tuple(
        NotePoolRow(note_id=n, subject_note="", project="---", assignee="p")
        for n in neighbours + [note_id] * copies
    )
    found = exact_row(NotePoolList(rows=rows, total=len(rows), pages=1), note_id)
    if copies == 1:
        assert found is not None and found.note_id == note_id
    else:
        assert found is None


# E6: the PR risk level (scripts/risk.py)

PATHS = st.lists(
    st.sampled_from(
        [
            "src/po_agent/mysys/guard.py",
            "src/po_agent/b1/address.py",
            "src/po_agent/core/run.py",
            "scripts/check.py",
            "scripts/heartbeat_check.py",
            "tests/test_risk.py",
            "docs/decisions.md",
            ".github/workflows/check.yml",
            ".claude/settings.json",
            "README.md",
        ]
    )
    | st.text(string.ascii_lowercase + "/._", min_size=1, max_size=30),
    max_size=6,
)


@given(PATHS, PATHS)
def test_adding_files_never_lowers_a_prs_risk(paths, more):
    assert risk.LEVELS.index(risk.assess(paths + more)) >= risk.LEVELS.index(
        risk.assess(paths)
    )


@given(PATHS)
def test_a_prs_risk_is_its_riskiest_files(paths):
    """risk.assess's contract: the PR's level is its highest file's."""
    level = risk.assess(paths)
    assert all(
        risk.LEVELS.index(risk.classify(p)) <= risk.LEVELS.index(level) for p in paths
    )
    assert level == "low" or level in {risk.classify(p) for p in paths}


@given(PATHS)
def test_windows_separators_never_change_a_files_risk(paths):
    for path in paths:
        assert risk.classify(path.replace("/", "\\")) == risk.classify(path)


@given(
    st.lists(
        st.tuples(
            st.integers(0, 999).map(str) | st.just("-"),
            st.integers(0, 999).map(str) | st.just("-"),
            st.text(string.ascii_letters + "/._ ", min_size=1, max_size=20),
        ),
        max_size=6,
    )
)
def test_numstat_rows_round_trip(rows):
    """git diff --numstat: binary files show "-" and count 0."""
    text = "\n".join("\t".join(row) for row in rows)
    paths, lines = risk.parse_numstat(text)
    assert paths == [path for _, _, path in rows]
    assert lines == sum(int(n) for a, d, _ in rows for n in (a, d) if n != "-")

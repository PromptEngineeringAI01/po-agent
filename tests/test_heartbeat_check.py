"""Tests for scripts/heartbeat_check.py, the scheduled missed-heartbeat check
(plan task 7.1). Offline: only its age, window and parse logic."""

import importlib.util
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PERTH = timezone(timedelta(hours=8))


@pytest.fixture(scope="module")
def hb():
    # scripts/ isn't a package, so load the file directly.
    spec = importlib.util.spec_from_file_location(
        "heartbeat_check", ROOT / "scripts" / "heartbeat_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def perth(day: int, hour: int, minute: int = 0) -> datetime:
    """A time in Perth in the week of Monday 2 Nov 2026 (day 2 = Monday)."""
    return datetime(2026, 11, day, hour, minute, tzinfo=PERTH)


LAST_FRIDAY = datetime(2026, 10, 30, 17, 25, tzinfo=PERTH)  # the 17:07 run's ping


@pytest.mark.parametrize(
    ("now", "last_ping", "missed"),
    (
        # Inside the window: more than 2 hours alerts, 2 hours or less doesn't.
        (perth(3, 10, 0), perth(3, 8, 30), False),
        (perth(3, 10, 31), perth(3, 8, 30), True),
        (perth(3, 10, 30), perth(3, 8, 30), False),
        # The last run of the day (17:07) missed: caught up to 19:07.
        (perth(3, 19, 0), perth(3, 16, 30), True),
        (perth(3, 19, 0), perth(3, 17, 25), False),
        # Monday morning: the weekend gap doesn't alert before 09:07 ...
        (perth(2, 9, 6), LAST_FRIDAY, False),
        # ... but no 07:07 or 08:07 ping by 09:07 does.
        (perth(2, 9, 7), LAST_FRIDAY, True),
        # Outside the window: nothing alerts, however old the ping.
        (perth(3, 6, 0), perth(2, 17, 20), False),
        (perth(3, 19, 8), perth(3, 16, 30), False),
        (perth(3, 23, 0), perth(3, 16, 30), False),
        (perth(7, 12, 0), perth(6, 17, 20), False),  # Saturday
        (perth(8, 12, 0), perth(6, 17, 20), False),  # Sunday
    ),
)
def test_missed_inside_the_window_only(hb, now, last_ping, missed):
    assert hb.missed(now.astimezone(UTC), last_ping.astimezone(UTC)) is missed


def test_no_heartbeat_issue_counts_as_missed_inside_the_window_only(hb):
    assert hb.missed(perth(4, 12, 0), None) is True
    assert hb.missed(perth(7, 12, 0), None) is False


def test_last_ping_is_the_newest_updated_at(hb):
    listed = (
        '[{"number": 7, "updatedAt": "2026-11-05T01:10:00Z"},'
        ' {"number": 9, "updatedAt": "2026-11-05T02:12:30Z"}]'
    )

    assert hb.last_ping(listed) == datetime(2026, 11, 5, 2, 12, 30, tzinfo=UTC)
    assert hb.last_ping("[]") is None


@pytest.mark.parametrize(
    ("missed", "open_titles", "opens"),
    (
        (True, [], True),
        (True, ["po-agent alert 20261105T000700Z-3fa2"], True),
        (True, ["po-agent heartbeat missed"], False),  # one open at a time
        (False, [], False),
    ),
)
def test_at_most_one_open_missed_heartbeat_issue(hb, missed, open_titles, opens):
    assert hb.should_open(missed, open_titles) is opens

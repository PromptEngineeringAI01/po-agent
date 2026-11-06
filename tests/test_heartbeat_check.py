"""Tests for scripts/heartbeat_check.py, the scheduled missed-heartbeat check
(plan task 7.1). Offline: its schedule-time, parse and dedupe logic, and main()
with a fake `gh`."""

import importlib.util
import json
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


# Each case counts the schedule time (today, Perth, 07:07-17:30: the 17:07
# run's ping comes by 17:30) since the last ping; more than 2 hours alerts.
@pytest.mark.parametrize(
    ("now", "last_ping", "missed"),
    (
        # During the day: more than 2 hours alerts, 2 hours or less doesn't.
        (perth(3, 10, 0), perth(3, 8, 30), False),
        (perth(3, 10, 31), perth(3, 8, 30), True),
        (perth(3, 10, 30), perth(3, 8, 30), False),
        # 16:07 and 17:07 missed: caught by any evening firing, however late.
        (perth(3, 19, 30), perth(3, 15, 25), True),
        (perth(3, 21, 0), perth(3, 15, 25), True),
        # Only 17:07 missed: 65 minutes of schedule time, no alert.
        (perth(3, 19, 37), perth(3, 16, 25), False),
        # A normal end of day, checked by a late firing.
        (perth(3, 19, 45), perth(3, 17, 25), False),
        # Monday morning: only today's schedule counts, so 09:07 is 2 hours ...
        (perth(2, 9, 7), LAST_FRIDAY, False),
        # ... and no 07:07 or 08:07 ping by 09:08 alerts.
        (perth(2, 9, 8), LAST_FRIDAY, True),
        # Yesterday's gap doesn't carry into the first 2 hours of a day.
        (perth(3, 6, 0), perth(2, 15, 0), False),
        (perth(3, 9, 0), perth(2, 15, 0), False),
        (perth(7, 12, 0), perth(6, 17, 20), False),  # Saturday
        (perth(8, 12, 0), perth(6, 17, 20), False),  # Sunday
    ),
)
def test_missed_counts_only_schedule_time(hb, now, last_ping, missed):
    assert hb.missed(now.astimezone(UTC), last_ping.astimezone(UTC)) is missed


def test_no_ping_counts_from_the_start_of_today(hb):
    assert hb.missed(perth(4, 12, 0), None) is True
    assert hb.missed(perth(4, 9, 0), None) is False
    assert hb.missed(perth(7, 12, 0), None) is False


def test_last_ping_is_the_newest_last_run_line_in_a_body(hb):
    # The body's `last run:` time, not updatedAt: a comment, label or
    # cross-reference from anyone must not count as a ping.
    listed = json.dumps(
        [
            {"body": "last run: 2026-11-05T01:10:00Z\nexit code: 0\nrun_id: none"},
            {"body": "last run: 2026-11-05T02:12:30Z\nexit code: 1\nrun_id: none"},
            {"body": "no run yet"},
        ]
    )

    assert hb.last_ping(listed) == datetime(2026, 11, 5, 2, 12, 30, tzinfo=UTC)
    assert hb.last_ping(json.dumps([{"body": "no run yet"}])) is None
    assert hb.last_ping("[]") is None


PING = perth(3, 8, 25).astimezone(UTC)
BEFORE = (PING - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
AFTER = (PING + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
MISSED_TITLE = "po-agent heartbeat missed"


@pytest.mark.parametrize(
    ("missed", "open_alerts", "last_ping", "opens"),
    (
        (True, [], PING, True),
        (
            True,
            [{"title": "po-agent alert 20261105T000700Z-3fa2", "createdAt": AFTER}],
            PING,
            True,
        ),
        # This outage already has its open alert: no second one.
        (True, [{"title": MISSED_TITLE, "createdAt": AFTER}], PING, False),
        (True, [{"title": MISSED_TITLE, "createdAt": AFTER}], None, False),
        # An alert left open from an earlier outage doesn't hide a new one.
        (True, [{"title": MISSED_TITLE, "createdAt": BEFORE}], PING, True),
        (False, [], PING, False),
    ),
)
def test_one_open_alert_per_outage(hb, missed, open_alerts, last_ping, opens):
    assert hb.should_open(missed, json.dumps(open_alerts), last_ping) is opens


class FakeGh:
    """Stands in for `gh`: answers the two lists, records every call."""

    def __init__(self, heartbeat_bodies: list[str]):
        self.heartbeat = json.dumps([{"body": body} for body in heartbeat_bodies])
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, *args: str) -> str:
        self.calls.append(args)
        label = args[args.index("--label") + 1] if "--label" in args else None
        if args[:2] == ("issue", "list") and label == "po-agent-heartbeat":
            return self.heartbeat
        if args[:2] == ("issue", "list") and label == "po-agent-alert":
            return "[]"
        return ""


def test_main_opens_one_labelled_alert_when_missed(hb, monkeypatch):
    fake = FakeGh(["last run: 2026-11-03T00:25:00Z\nexit code: 0\nrun_id: none"])
    monkeypatch.setattr(hb, "gh", fake)

    assert hb.main(perth(3, 12, 0).astimezone(UTC)) == 0

    created = [call for call in fake.calls if call[:2] == ("issue", "create")]
    assert len(created) == 1
    (args,) = created
    assert args[args.index("--label") + 1] == "po-agent-alert"
    assert args[args.index("--title") + 1] == MISSED_TITLE
    heartbeat_list = fake.calls[0]
    assert heartbeat_list[heartbeat_list.index("--state") + 1] == "open"


def test_main_opens_nothing_when_a_ping_is_recent(hb, monkeypatch):
    fake = FakeGh(["last run: 2026-11-03T03:25:00Z\nexit code: 0\nrun_id: none"])
    monkeypatch.setattr(hb, "gh", fake)

    assert hb.main(perth(3, 12, 0).astimezone(UTC)) == 0

    assert not [call for call in fake.calls if call[:2] == ("issue", "create")]

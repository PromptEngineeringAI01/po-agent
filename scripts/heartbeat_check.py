"""The missed-heartbeat check (plan task 7.1), run by
.github/workflows/heartbeat.yml: `python3 scripts/heartbeat_check.py`.

The Mac Mini wrapper (scripts/macmini-run.sh) pings at the end of every run by
replacing the body of the one open issue labelled po-agent-heartbeat; its
first line is `last run: <UTC time>`. This script reads that time from the
body, never `updatedAt`, so a comment, label or cross-reference from anyone
can't pass for a ping (only repo writers can edit the body).

The schedule is Monday-Friday, runs at 07:07-17:07 Australia/Perth (UTC+8, no
DST); the 17:07 run's ping comes by 17:30, after its 20-minute limit. The
check counts only today's schedule time (07:07-17:30 Perth) since the last
ping, and more than 2 hours of it is a miss. So nothing alerts at night, at
the weekend or in a day's first 2 hours, a late or skipped cron firing only
delays the alert, and a normal end of day never alerts.

A miss opens one po-agent-alert issue (GitHub emails Joey). An open one that
was opened after the last ping already covers this outage, so no second one;
an open one from an earlier outage doesn't hide a new one. Standard library
and `gh` only; no PO data.
"""

import json
import re
import subprocess
import sys
from datetime import UTC, datetime, time, timedelta, timezone

PERTH = timezone(timedelta(hours=8))
DAY_START = time(7, 7)  # the first run
DAY_END = time(17, 30)  # the 17:07 run's ping, after its 20-minute limit
MAX_AGE = timedelta(hours=2)
HEARTBEAT_LABEL = "po-agent-heartbeat"
ALERT_LABEL = "po-agent-alert"
ALERT_TITLE = "po-agent heartbeat missed"
LAST_RUN = re.compile(r"^last run: (\S+)$", re.MULTILINE)


def schedule_time(since: datetime | None, now: datetime) -> timedelta:
    """Today's (Perth) schedule time between `since` (None: all day) and `now`."""
    today = now.astimezone(PERTH)
    if today.weekday() >= 5:
        return timedelta(0)
    start = datetime.combine(today.date(), DAY_START, PERTH)
    end = min(now, datetime.combine(today.date(), DAY_END, PERTH))
    if since is not None:
        start = max(start, since)
    return max(end - start, timedelta(0))


def missed(now: datetime, last_ping: datetime | None) -> bool:
    """More than MAX_AGE of today's schedule time without a ping."""
    return schedule_time(last_ping, now) > MAX_AGE


def last_ping(listed: str) -> datetime | None:
    """The newest `last run:` time in `gh issue list --json body` output."""
    times = []
    for issue in json.loads(listed):
        match = LAST_RUN.search(issue.get("body") or "")
        if not match:
            continue
        try:
            when = datetime.fromisoformat(match.group(1))
        except ValueError:
            continue
        if when.tzinfo is not None:
            times.append(when)
    return max(times, default=None)


def should_open(missed_now: bool, open_alerts: str, ping: datetime | None) -> bool:
    """Missed, and no open missed-heartbeat alert opened after the last ping
    (`open_alerts` is `gh issue list --json title,createdAt` output)."""
    for alert in json.loads(open_alerts):
        if alert["title"] != ALERT_TITLE:
            continue
        if ping is None or datetime.fromisoformat(alert["createdAt"]) > ping:
            return False
    return missed_now


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=True
    ).stdout


def main(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    heartbeat = gh(
        "issue", "list", "--label", HEARTBEAT_LABEL, "--state", "open",
        "--json", "body",
    )  # fmt: skip
    ping = last_ping(heartbeat)
    if not missed(now, ping):
        print(f"heartbeat: ok (last ping {ping})")
        return 0
    open_alerts = gh(
        "issue", "list", "--label", ALERT_LABEL, "--state", "open",
        "--limit", "200", "--json", "title,createdAt",
    )  # fmt: skip
    if not should_open(True, open_alerts, ping):
        print(f"heartbeat: missed (last ping {ping}); alert already open")
        return 0
    last = ping.strftime("%Y-%m-%dT%H:%M:%SZ") if ping else "none found"
    body = (
        "No po-agent heartbeat for over 2 hours inside the schedule "
        "(Monday-Friday, 07:07-17:07 Perth).\n"
        f"last ping: {last}\n"
        "Close this issue once runs are back."
    )
    gh(
        "issue", "create", "--label", ALERT_LABEL, "--title", ALERT_TITLE,
        "--body", body,
    )  # fmt: skip
    print(f"heartbeat: missed (last ping {ping}); alert opened")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The missed-heartbeat check (plan task 7.1), run by
.github/workflows/heartbeat.yml: `python3 scripts/heartbeat_check.py`.

The Mac Mini wrapper (scripts/macmini-run.sh) pings at the end of every run by
editing the body of the one open issue labelled po-agent-heartbeat. This
script reads that issue's `updatedAt` (GitHub's clock, not the Mac's) and, if
no ping has come for more than 2 hours inside the schedule, opens one
po-agent-alert issue (GitHub emails Joey), never a second while one is open.

The schedule is Monday-Friday, runs at 07:07-17:07 Australia/Perth (UTC+8, no
DST). "Inside the schedule" means the 2 hours before now lie in one weekday's
07:07-17:07, so it checks only from 09:07 to 19:07 Perth on a weekday: the
weekend gap and the first two runs of a day never alert, and a missed 17:07
run still does. The age comes from timestamps, so a late or skipped cron
firing changes nothing but when the check runs. Standard library and `gh`
only; the issue holds no PO data.
"""

import json
import subprocess
import sys
from datetime import UTC, datetime, time, timedelta, timezone

PERTH = timezone(timedelta(hours=8))
FIRST_RUN = time(7, 7)
LAST_RUN = time(17, 7)
MAX_AGE = timedelta(hours=2)
HEARTBEAT_LABEL = "po-agent-heartbeat"
ALERT_LABEL = "po-agent-alert"
ALERT_TITLE = "po-agent heartbeat missed"


def in_window(now: datetime) -> bool:
    """Whether the MAX_AGE before `now` lie inside one weekday's schedule."""
    start = (now - MAX_AGE).astimezone(PERTH)
    end = now.astimezone(PERTH)
    return (
        start.weekday() < 5
        and start.date() == end.date()
        and FIRST_RUN <= start.time() <= LAST_RUN
    )


def missed(now: datetime, last_ping: datetime | None) -> bool:
    """No ping for more than MAX_AGE inside the schedule (none at all counts)."""
    if not in_window(now):
        return False
    return last_ping is None or now - last_ping > MAX_AGE


def last_ping(listed: str) -> datetime | None:
    """The newest `updatedAt` in `gh issue list --json updatedAt` output."""
    times = [datetime.fromisoformat(issue["updatedAt"]) for issue in json.loads(listed)]
    return max(times, default=None)


def should_open(missed_now: bool, open_alert_titles: list[str]) -> bool:
    """Open an alert only if missed and no missed-heartbeat alert is open."""
    return missed_now and ALERT_TITLE not in open_alert_titles


def gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=True
    ).stdout


def main() -> int:
    now = datetime.now(UTC)
    ping = last_ping(
        gh(
            "issue",
            "list",
            "--label",
            HEARTBEAT_LABEL,
            "--state",
            "open",
            "--json",
            "updatedAt",
        )
    )
    if not missed(now, ping):
        print(f"heartbeat: ok (last ping {ping})")
        return 0
    open_titles = [
        issue["title"]
        for issue in json.loads(
            gh(
                "issue",
                "list",
                "--label",
                ALERT_LABEL,
                "--state",
                "open",
                "--limit",
                "200",
                "--json",
                "title",
            )
        )
    ]
    if not should_open(True, open_titles):
        print(f"heartbeat: missed (last ping {ping}); alert already open")
        return 0
    last = (
        ping.strftime("%Y-%m-%dT%H:%M:%SZ")
        if ping
        else "none (no open heartbeat issue)"
    )
    body = (
        "No po-agent heartbeat for over 2 hours inside the schedule "
        "(Monday-Friday, 07:07-17:07 Perth).\n"
        f"last ping: {last}\n"
        "Close this issue once runs are back; the next miss opens a new one."
    )
    gh(
        "issue",
        "create",
        "--label",
        ALERT_LABEL,
        "--title",
        ALERT_TITLE,
        "--body",
        body,
    )
    print(f"heartbeat: missed (last ping {ping}); alert opened")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Every MySys wait: polled until a read is true, read until settled, and
the one retry of an opening click (task 8.4; docs/architecture-review.md
Round 2 C, Joey's settled design, 9 Nov 2026).

The polls run on one clock: `PageClock` (time.monotonic, and the page's own
wait so Playwright keeps handling the page's events) or a fake in tests.
The timeouts live here, once; the driver and booking read them at call time,
so a test sets each one in one place.

The retry refuses a committing click. It takes only the opening actions in
`OpeningAction` (an opening click changes nothing in MySys) and raises
before the guard is asked for any other name: committing clicks (Submit,
the Hold confirm, the Choose Project cell, Solved, each Assign, Upload, ...)
are made once, never retried (decisions, 3 Nov 2026, M4 gate). The set lives
here, not in the guard. Every click still goes through `guard.act`.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, Self, get_args

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page

from po_agent.core.errors import UnexpectedScreen
from po_agent.mysys.guard import ActionGuard

LOAD_TIMEOUT_MS = 15_000  # a window, a label, a read-back, a settled table
POLL_MS = 500
# Live 28 Oct 2026: the Choose Project window's content showed only after a
# 15 s wait had given up.
LINK_TIMEOUT_MS = 60_000
# The Projects search: Joey saw pauses of about 10 s (28 Oct 2026).
SEARCH_TIMEOUT_MS = 60_000
EMPTY_SETTLE_MS = 3000  # My Notes: how long an empty list must stay empty
OPEN_TRIES = 4  # x the page's 15 s
MENU_TRIES = 3
MENU_ITEM_MS = 2000  # a Project menu item, after each Project click

# The clicks the retry may make again: each opens or refreshes a view.
OpeningAction = Literal[
    "open_note", "open_project", "open_project_tab", "refresh_note_pool"
]
OPENING_ACTIONS: frozenset[str] = frozenset(get_args(OpeningAction))


class Clock(Protocol):
    def now(self) -> float:
        """Seconds, never going back."""
        ...

    def sleep(self, ms: int) -> None: ...


@dataclass(frozen=True)
class PageClock:
    page: Page

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, ms: int) -> None:
        self.page.wait_for_timeout(ms)


@dataclass(frozen=True)
class Deadline:
    """A point on `clock`; one deadline can be shared by several waits."""

    clock: Clock
    at: float

    @classmethod
    def after(cls, clock: Clock, ms: int) -> Self:
        return cls(clock, clock.now() + ms / 1000)

    def passed(self) -> bool:
        return self.clock.now() >= self.at

    def pause(self) -> None:
        self.clock.sleep(POLL_MS)


def within(page: Page, ms: int | None = None) -> Deadline:
    """A deadline `ms` from now (default LOAD_TIMEOUT_MS) on the page's clock."""
    return Deadline.after(PageClock(page), LOAD_TIMEOUT_MS if ms is None else ms)


def until(deadline: Deadline, read: Callable[[], bool]) -> bool:
    """Reads every POLL_MS until `read` is true (True), or the deadline has
    passed (False; the last read is at or after it). A read that fails for a
    moment (UnexpectedScreen, a Playwright error: the window re-rendering)
    is read again; any other error goes through."""
    while True:
        try:
            if read():
                return True
        except (UnexpectedScreen, PlaywrightError):
            pass
        if deadline.passed():
            return False
        deadline.pause()


def settled[T](
    deadline: Deadline,
    read: Callable[[], T | None],
    counts: Callable[[T], bool],
    reads: int = 2,
) -> T | None:
    """The value once `reads` reads in a row are equal and `counts` takes
    them; None once the deadline has passed. A read of None (not readable
    now: `read` turns its own errors into None) or one `counts` refuses
    starts the count again."""
    last: T | None = None
    same = 0
    while True:
        value = read()
        if value is not None and counts(value):
            same = same + 1 if same and value == last else 1
            if same >= reads:
                return value
            last = value
        else:
            last, same = None, 0
        if deadline.passed():
            return None
        deadline.pause()


def retry_opening(
    guard: ActionGuard,
    action: OpeningAction,
    scope: Locator,
    target: Locator,
    *,
    tries: int | None = None,
    shown: Callable[[], bool] | None = None,
) -> bool:
    """An opening click, made again if it did not take. Any action not in
    OPENING_ACTIONS raises ValueError before the guard is asked.

    Without `shown`: tried up to `tries` (default OPEN_TRIES) times while
    the page is still covered (see driver.leave_menu): Playwright never
    clicks a covered target, so a retry can't act twice; the last
    UnexpectedScreen is raised. With `shown`: clicked up to `tries` times
    until `shown()` is true (True), else False; a failed click is not
    retried (the Project menu loops). A guard refusal is never retried.
    Silent: it prints nothing."""
    if action not in OPENING_ACTIONS:
        raise ValueError(f"not an opening action: {action}")
    tries = OPEN_TRIES if tries is None else tries
    for attempt in range(tries):
        if shown is not None:
            guard.act(action, scope, target)
            if shown():
                return True
            continue
        try:
            guard.act(action, scope, target)
            return True
        except UnexpectedScreen:
            if attempt == tries - 1:
                raise
    return False

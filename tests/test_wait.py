"""The one MySys wait module (task 8.4; docs/architecture-review.md Round 2 C).

`until` and `settled` run on a fake clock and a list of reads: no browser.
The opening-click retry runs on a local page with the real guard: it must
refuse every committing click before the guard is asked (3 Nov 2026, M4
gate: committing clicks are made once, never retried).

Values are fake.
"""

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, Page
from playwright.sync_api import Error as PlaywrightError

from po_agent.core.errors import GuardRefusal, UnexpectedScreen
from po_agent.mysys import wait
from po_agent.mysys.guard import ALLOWLIST, ActionGuard, Kind


class FakeClock:
    """Seconds that pass only when the wait sleeps."""

    def __init__(self) -> None:
        self.time = 0.0
        self.slept: list[int] = []

    def now(self) -> float:
        return self.time

    def sleep(self, ms: int) -> None:
        self.slept.append(ms)
        self.time += ms / 1000


def reads(*values: object) -> Callable[[], object]:
    """A read that returns `values` in turn (an exception value is raised),
    then the last value forever."""
    queue = list(values)

    def read() -> object:
        value = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(value, BaseException):
            raise value
        return value

    return read


def deadline(ms: int = wait.LOAD_TIMEOUT_MS) -> tuple[wait.Deadline, FakeClock]:
    clock = FakeClock()
    return wait.Deadline.after(clock, ms), clock


# The timeouts, once, with today's values


def test_the_waits_keep_todays_values() -> None:
    assert (wait.LOAD_TIMEOUT_MS, wait.POLL_MS) == (15_000, 500)
    assert (wait.LINK_TIMEOUT_MS, wait.SEARCH_TIMEOUT_MS) == (60_000, 60_000)
    assert (wait.OPEN_TRIES, wait.MENU_TRIES, wait.MENU_ITEM_MS) == (4, 3, 2000)
    assert wait.EMPTY_SETTLE_MS == 3000


# until: polled until a read is true


def test_until_is_true_at_the_first_true_read() -> None:
    limit, clock = deadline()
    assert wait.until(limit, reads(False, False, True))
    assert clock.slept == [wait.POLL_MS, wait.POLL_MS]


def test_until_reads_again_after_a_read_that_fails_for_a_moment() -> None:
    # driver._polls: a label gone for a moment (the window re-rendering).
    limit, _ = deadline()
    read = reads(UnexpectedScreen("gone"), PlaywrightError("detached"), True)
    assert wait.until(limit, read)


def test_until_lets_any_other_error_through() -> None:
    limit, _ = deadline()
    with pytest.raises(GuardRefusal):
        wait.until(limit, reads(GuardRefusal("refused")))


def test_until_is_false_once_the_deadline_has_passed_and_read_last_then() -> None:
    limit, clock = deadline()
    seen: list[float] = []

    def read() -> bool:
        seen.append(clock.time)
        return False

    assert not wait.until(limit, read)
    assert seen[-1] == 15.0  # one read at the deadline, none after it
    assert len(seen) == 31  # every 500 ms from 0 to 15 s


def test_until_waits_as_long_as_its_deadline() -> None:
    limit, clock = deadline(wait.SEARCH_TIMEOUT_MS)
    assert not wait.until(limit, reads(False))
    assert clock.time == 60.0


# settled: N equal reads in a row that the predicate takes


def test_settled_is_the_value_read_twice_in_a_row() -> None:
    limit, _ = deadline()
    assert wait.settled(limit, reads("a", "b", "b"), lambda v: True) == "b"


def test_settled_starts_again_after_a_read_it_does_not_take() -> None:
    limit, clock = deadline()
    # "a", then a half-rendered read (None), then "a" again: not yet settled.
    read = reads("a", None, "a", "x", "x")
    assert wait.settled(limit, read, lambda v: v != "x") is None
    limit, clock = deadline()
    read = reads("a", "skip", "a", "a")
    assert wait.settled(limit, read, lambda v: v != "skip") == "a"
    assert len(clock.slept) == 3


def test_settled_can_ask_for_more_equal_reads() -> None:
    limit, clock = deadline()
    assert wait.settled(limit, reads(1, 1, 2, 2, 2), lambda v: True, reads=3) == 2
    assert len(clock.slept) == 4


def test_settled_is_none_at_the_deadline() -> None:
    limit, clock = deadline()
    counter = iter(range(1000))
    assert wait.settled(limit, lambda: next(counter), lambda v: True) is None
    assert clock.time == 15.0


def test_settled_shares_its_deadline_across_calls() -> None:
    # The Projects search reads settled lists against one 60 s deadline.
    limit, clock = deadline(wait.SEARCH_TIMEOUT_MS)
    assert wait.settled(limit, reads(1, 1), lambda v: True) == 1
    clock.time = 60.0
    assert wait.settled(limit, reads(2, 2), lambda v: True) is None
    assert clock.slept == [wait.POLL_MS]


# The opening-click retry


def test_the_opening_actions_are_todays_retried_clicks() -> None:
    # Adding one is a decision (docs/decisions.md): a committing click is
    # never retried.
    assert wait.OPENING_ACTIONS == {
        "open_note",
        "refresh_note_pool",
        "open_project",
        "open_project_tab",
    }
    assert all(ALLOWLIST[name] is Kind.CLICK for name in wait.OPENING_ACTIONS)


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    page = browser.new_page()
    page.set_default_timeout(2000)
    yield page
    page.close()


@pytest.mark.parametrize("action", sorted(set(ALLOWLIST) - wait.OPENING_ACTIONS))
def test_the_retry_refuses_every_other_action_before_the_guard(
    page: Page, action: str
) -> None:
    # Submit, Assign, the Choose Project cell, Solved, Hold, Upload, ...
    page.set_content('<button onclick="this.dataset.clicked = 1">Go</button>')
    button = page.get_by_role("button", name="Go", exact=True)
    guard = ActionGuard()
    with pytest.raises(ValueError, match="not an opening action"):
        wait.retry_opening(guard, action, page.locator("body"), button)
    assert guard.history == []
    assert button.get_attribute("data-clicked") is None


BLOCKED_PAGE = """
<div id="cover" style="position: fixed; inset: 0; z-index: 10"></div>
<button onclick="this.dataset.clicked = (+this.dataset.clicked || 0) + 1"
  >Refresh</button>
"""


def test_a_covered_opening_click_is_tried_open_tries_times_then_raises(
    page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(wait, "OPEN_TRIES", 2)
    page.set_default_timeout(300)
    page.set_content(BLOCKED_PAGE)
    refresh = page.get_by_role("button", name="Refresh", exact=True)
    guard = ActionGuard()
    with pytest.raises(UnexpectedScreen):
        wait.retry_opening(guard, "refresh_note_pool", page.locator("body"), refresh)
    assert guard.history == [("refresh_note_pool", "failed")] * 2
    assert refresh.get_attribute("data-clicked") is None


def test_a_guard_refusal_is_never_retried(page: Page) -> None:
    page.set_content("<button>Delete</button>")  # Delete: on the denylist
    delete = page.get_by_role("button", name="Delete", exact=True)
    guard = ActionGuard()
    with pytest.raises(GuardRefusal):
        wait.retry_opening(guard, "open_project", page.locator("body"), delete)
    assert len(guard.history) == 1


COUNTED_PAGE = """
<button onclick="this.dataset.clicked = (+this.dataset.clicked || 0) + 1"
  >Project</button>
"""


def test_a_menu_click_is_made_again_until_its_item_shows(page: Page) -> None:
    page.set_content(COUNTED_PAGE)
    title = page.get_by_role("button", name="Project", exact=True)

    def clicks() -> int:
        return int(title.get_attribute("data-clicked") or 0)

    guard = ActionGuard()
    assert wait.retry_opening(
        guard,
        "open_project_tab",
        page.locator("body"),
        title,
        tries=wait.MENU_TRIES,
        shown=lambda: clicks() == 2,
    )
    assert clicks() == 2


def test_a_menu_item_that_never_shows_is_false_after_menu_tries(page: Page) -> None:
    page.set_content(COUNTED_PAGE)
    title = page.get_by_role("button", name="Project", exact=True)
    guard = ActionGuard()
    shown = wait.retry_opening(
        guard,
        "open_project_tab",
        page.locator("body"),
        title,
        tries=wait.MENU_TRIES,
        shown=lambda: False,
    )
    assert not shown
    assert title.get_attribute("data-clicked") == str(wait.MENU_TRIES)


def test_a_failed_menu_click_is_not_retried(
    page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Today's menu loops let the click's own error through at once.
    page.set_default_timeout(300)
    page.set_content(BLOCKED_PAGE.replace("Refresh", "Project"))
    title = page.get_by_role("button", name="Project", exact=True)
    guard = ActionGuard()
    with pytest.raises(UnexpectedScreen):
        wait.retry_opening(
            guard,
            "open_project_tab",
            page.locator("body"),
            title,
            tries=wait.MENU_TRIES,
            shown=lambda: True,
        )
    assert guard.history == [("open_project_tab", "failed")]

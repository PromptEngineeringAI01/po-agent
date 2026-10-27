"""The run modes (SPEC.md -> In the MVP). 1.8 builds the spike; M3 adds the
Note loop for decide-only and run.

The Note Pool is read once per run: later steps work through that fixed list
of Note IDs, so a Note skipped and returned to the pool isn't taken again in
the same run. Output is counts only (core/output.py).
"""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass

from po_agent.b1.decision import TitleRule, eligible_internal_no
from po_agent.b1.models import NotePoolRow
from po_agent.core import output
from po_agent.core.config import Config
from po_agent.core.secrets import SecretName
from po_agent.mysys import driver
from po_agent.mysys.guard import ActionGuard


@dataclass(frozen=True)
class EligibleNote:
    note_id: str
    internal_no: str


def eligible_notes(
    rows: Sequence[NotePoolRow], rule: TitleRule, pool_name: str
) -> tuple[EligibleNote, ...]:
    """Step 0 on every row, in list order (newest first)."""
    found = []
    for row in rows:
        internal_no = eligible_internal_no(row, rule, pool_name)
        if internal_no is not None:
            found.append(EligibleNote(note_id=row.note_id, internal_no=internal_no))
    return tuple(found)


def spike(
    config: Config,
    credentials: dict[SecretName, str],
    options: argparse.Namespace,
    summary: output.RunSummary,
) -> int:
    """Log in, filter and read the Note Pool once, print counts. Read-only."""
    guard = ActionGuard()
    with driver.open_browser(headed=options.headed, slow_mo=options.slow_mo) as page:
        driver.go_home(page, str(config.base_url))
        driver.login(
            guard,
            page,
            credentials["mysys_test_username"],
            credentials["mysys_test_password"],
        )
        output.info("logged in")
        panel = driver.open_note_pool(guard, page)
        driver.set_note_pool_filters(guard, panel, config.pool_name)
        output.info("note pool filters set")
        listing = driver.read_note_pool(guard, panel)
    found = eligible_notes(listing.rows, config.title_rule, config.pool_name)
    summary.seen = len(listing.rows)
    summary.eligible = len(found)
    output.info(
        "note pool read: {rows} rows, {eligible} eligible",
        rows=len(listing.rows),
        eligible=len(found),
    )
    if listing.pages > 1:
        output.info(
            "note pool has more pages: only page 1 of {pages} read",
            pages=listing.pages,
        )
    return 0

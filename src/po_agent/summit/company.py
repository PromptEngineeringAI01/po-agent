"""Summit's company names against the creator table (task 9.9; SPEC.md ->
Client 2: Summit Home, Creator table).

Pure. A name names a table row when it equals the row's name or one of its
aliases, trimmed and case-insensitive, whole name only. A name not in the
table names no row: COMPANY_UNKNOWN, so a missing alias costs coverage,
never a wrong write. The table itself is the client file's
(`config/clients/summit.toml`, checked by `core/config.py`: every name and
alias names one row only).
"""

from collections.abc import Sequence

from po_agent.core.config import Company


def fold(name: str) -> str:
    """A name or cell as it is compared: trimmed, case-folded."""
    return name.strip().casefold()


def row_for(name: str, table: Sequence[Company]) -> Company | None:
    """The table row `name` names, None when it names none."""
    wanted = fold(name)
    if not wanted:
        return None
    for company in table:
        if wanted in {fold(n) for n in (company.name, *company.aliases)}:
            return company
    return None

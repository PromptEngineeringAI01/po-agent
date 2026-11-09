"""Typed errors and their exit codes (SPEC.md -> Code style, Exit codes).

A message is a fixed detail written in the code plus identifiers only (action
name, step, note_id, trial pln, config field, secret name, guard refusal
reason). Never pass an element's text, a page string or a Playwright message:
they can hold an address (a "... Close" street behind a guard refusal).
scripts/guard_check.py fails on a detail that isn't a string constant. An
identifier that doesn't look like one is replaced by "<redacted>".

Each class declares its exit code and its ALERT kind (cli._report prints
`ALERT <alert_kind>`); the kinds are the stdout contract's `AlertKind`
(core/output.py, which imports this module, so only the type checker reads
it here).
"""

import re
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from po_agent.core.output import AlertKind

REDACTED = "<redacted>"
# Note IDs, steps, action names, plns, PO numbers (2609034B/048), field paths.
_IDENTIFIER = re.compile(r"[A-Za-z0-9_./-]{1,64}")
_IDENTIFIER_NAMES = ("action", "step", "note_id", "pln", "field", "secret", "reason")


def identifier(value: str | None) -> str | None:
    if value is None:
        return None
    return value if _IDENTIFIER.fullmatch(value) else REDACTED


class PoAgentError(Exception):
    exit_code: ClassVar[int] = 1
    alert_kind: ClassVar["AlertKind"] = "UNEXPECTED_SCREEN"

    def __init__(
        self,
        detail: str,
        *,
        action: str | None = None,
        step: str | None = None,
        note_id: str | None = None,
        pln: str | None = None,
        field: str | None = None,
        secret: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.detail = detail
        self.action = identifier(action)
        self.step = identifier(step)
        self.note_id = identifier(note_id)
        self.pln = identifier(pln)
        self.field = identifier(field)
        self.secret = identifier(secret)
        self.reason = identifier(reason)
        ids = ", ".join(
            f"{name}={getattr(self, name)}"
            for name in _IDENTIFIER_NAMES
            if getattr(self, name) is not None
        )
        super().__init__(f"{detail} ({ids})" if ids else detail)


class UnexpectedScreen(PoAgentError):
    exit_code = 1
    alert_kind = "UNEXPECTED_SCREEN"


class MorePages(UnexpectedScreen):
    """The Note Pool has a second page, which is never read: ALERT
    MORE_PAGES, exit 1, before any Note is taken (7.2; decisions, 5 Nov
    2026)."""

    exit_code = 1
    alert_kind = "MORE_PAGES"


class WriteNotStarted(PoAgentError):
    """No ALERT kind of its own: the run stops (exit 1), as for an
    unexpected screen."""

    exit_code = 1
    alert_kind = "UNEXPECTED_SCREEN"


class PartialWrite(PoAgentError):
    exit_code = 1
    alert_kind = "PARTIAL_WRITE"


class GuardRefusal(PoAgentError):
    exit_code = 1
    alert_kind = "GUARD_REFUSAL"


class LoginFailed(PoAgentError):
    exit_code = 2
    alert_kind = "LOGIN_FAILED"


class ConfigError(PoAgentError):
    exit_code = 2
    alert_kind = "CONFIG"


class AccuracyBreach(PoAgentError):
    exit_code = 3
    alert_kind = "ACCURACY_BREACH"


# 0 run finished · 1 run stopped · 2 config, secrets or login · 3 accuracy breach
EXIT_CODES: dict[type[PoAgentError], int] = {
    error_type: error_type.exit_code
    for error_type in (
        UnexpectedScreen,
        WriteNotStarted,
        PartialWrite,
        GuardRefusal,
        LoginFailed,
        ConfigError,
        AccuracyBreach,
    )
}

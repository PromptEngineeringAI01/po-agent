"""Typed errors and their exit codes (SPEC.md -> Code style, Exit codes).

A message is a fixed detail written in the code plus identifiers only (action
name, step, note_id, trial pln, config field, secret name, guard refusal
reason). Never pass an element's text, a page string or a Playwright message:
they can hold an address (a "... Close" street behind a guard refusal).
scripts/guard_check.py fails on a detail that isn't a string constant. An
identifier that doesn't look like one is replaced by "<redacted>".
"""

import re
from typing import ClassVar

REDACTED = "<redacted>"
# Note IDs, steps, action names, plns, PO numbers (2609034B/048), field paths.
_IDENTIFIER = re.compile(r"[A-Za-z0-9_./-]{1,64}")
_IDENTIFIER_NAMES = ("action", "step", "note_id", "pln", "field", "secret", "reason")


def _identifier(value: str | None) -> str | None:
    if value is None:
        return None
    return value if _IDENTIFIER.fullmatch(value) else REDACTED


class PoAgentError(Exception):
    exit_code: ClassVar[int] = 1

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
        self.action = _identifier(action)
        self.step = _identifier(step)
        self.note_id = _identifier(note_id)
        self.pln = _identifier(pln)
        self.field = _identifier(field)
        self.secret = _identifier(secret)
        self.reason = _identifier(reason)
        ids = ", ".join(
            f"{name}={getattr(self, name)}"
            for name in _IDENTIFIER_NAMES
            if getattr(self, name) is not None
        )
        super().__init__(f"{detail} ({ids})" if ids else detail)


class UnexpectedScreen(PoAgentError):
    exit_code = 1


class WriteNotStarted(PoAgentError):
    exit_code = 1


class PartialWrite(PoAgentError):
    exit_code = 1


class GuardRefusal(PoAgentError):
    exit_code = 1


class LoginFailed(PoAgentError):
    exit_code = 2


class ConfigError(PoAgentError):
    exit_code = 2


class AccuracyBreach(PoAgentError):
    exit_code = 3


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

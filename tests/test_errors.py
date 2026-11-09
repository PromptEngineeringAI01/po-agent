"""Each error class declares its ALERT kind next to its exit code (task 8.2).

cli._report prints `ALERT <error.alert_kind>`; the kind must be one of the
stdout contract's `AlertKind` (core/output.py).
"""

from typing import get_args

from po_agent.core.errors import (
    AccuracyBreach,
    ConfigError,
    GuardRefusal,
    LoginFailed,
    MorePages,
    PartialWrite,
    PoAgentError,
    UnexpectedScreen,
    WriteNotStarted,
)
from po_agent.core.output import AlertKind


def _all_subclasses(cls: type) -> list[type]:
    found = []
    for sub in cls.__subclasses__():
        found += [sub, *_all_subclasses(sub)]
    return found


def test_each_error_class_declares_its_alert_kind():
    kinds = {cls: cls.alert_kind for cls in _all_subclasses(PoAgentError)}
    assert kinds == {
        UnexpectedScreen: "UNEXPECTED_SCREEN",
        MorePages: "MORE_PAGES",
        WriteNotStarted: "UNEXPECTED_SCREEN",
        PartialWrite: "PARTIAL_WRITE",
        GuardRefusal: "GUARD_REFUSAL",
        LoginFailed: "LOGIN_FAILED",
        ConfigError: "CONFIG",
        AccuracyBreach: "ACCURACY_BREACH",
    }


def test_every_alert_kind_is_in_the_stdout_contract():
    for cls in [PoAgentError, *_all_subclasses(PoAgentError)]:
        assert cls.alert_kind in get_args(AlertKind), cls.__name__

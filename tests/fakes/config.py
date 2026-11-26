"""Config-file helpers shared by the offline tests.

A test that needs a kill switch on or off sets it here, so it pins the
behaviour and not the committed value of `config/clients/summit.toml` or a
site file, which its own PR flips (S.2; decisions, 26 Nov 2026).
"""

import re

_ENABLED = re.compile(r"(?m)^enabled = (true|false)\b")


def switched(text: str, on: bool) -> str:
    """`text`, a site or client TOML file, with its one `enabled` line set to
    `on`, whatever the file says now."""
    out, count = _ENABLED.subn(f"enabled = {'true' if on else 'false'}", text)
    assert count == 1, "expected exactly one `enabled = true|false` line"
    return out

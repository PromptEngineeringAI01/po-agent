"""Secrets at run time: env var PO_AGENT_<NAME> first, else keyring service
"po-agent" (CLAUDE.md -> Conventions, Secrets). No other env var is read.
Each site has its own MySys pair (decisions, 10 Nov 2026, live profile), and
each client its own: Summit logs in as Agent 2, live only (decisions, 23 Nov
2026, separate run). The live pairs are only in poagent's Keychain on the
Mac Mini, set by Joey.

Values are returned, never logged or put in an error message.
"""

import os
from typing import Literal, get_args

import keyring
from keyring.errors import KeyringError

from po_agent.core.errors import ConfigError

SecretName = Literal[
    "mysys_test_username",
    "mysys_test_password",
    "mysys_live_username",
    "mysys_live_password",
    "mysys_live_summit_username",
    "mysys_live_summit_password",
]
SECRET_NAMES: tuple[str, ...] = get_args(SecretName)
KEYRING_SERVICE = "po-agent"
ENV_PREFIX = "PO_AGENT_"


# (site, client) -> the MySys (username, password) pair. Summit has no
# test-site pair: it runs on live only.
_MYSYS_NAMES: dict[tuple[str, str], tuple[SecretName, SecretName]] = {
    ("test", "b1"): ("mysys_test_username", "mysys_test_password"),
    ("live", "b1"): ("mysys_live_username", "mysys_live_password"),
    ("live", "summit"): ("mysys_live_summit_username", "mysys_live_summit_password"),
}


def mysys_names(site: str, client: str = "b1") -> tuple[SecretName, SecretName]:
    """The client's MySys (username, password) secret names on that site;
    ValueError for a site or client without a pair."""
    if (site, client) not in _MYSYS_NAMES:
        raise ValueError("no MySys secrets for that site and client")
    return _MYSYS_NAMES[(site, client)]


def _find(name: SecretName) -> str | None:
    """The value, or None when it isn't set; ConfigError if the store can't
    be read."""
    if name not in SECRET_NAMES:
        raise ValueError("unknown secret name")
    value = os.environ.get(ENV_PREFIX + name.upper())
    if value:
        return value
    try:
        # Returns None when the entry doesn't exist; backend failures raise
        # KeyringError or a subclass such as NoKeyringError
        # (https://keyring.readthedocs.io/en/latest/, "API" and "Exceptions").
        return keyring.get_password(KEYRING_SERVICE, name) or None
    except KeyringError:
        # from None: the backend's message stays out of the error chain.
        raise ConfigError("secret store unavailable", secret=name) from None


def get(name: SecretName) -> str:
    """The secret's value; ConfigError (naming the secret) if it isn't set."""
    value = _find(name)
    if not value:
        raise ConfigError("secret not set (env var or keyring)", secret=name)
    return value


SecretStatus = Literal["ok", "not set", "malformed", "store unavailable"]


def inspect(name: SecretName) -> SecretStatus:
    """Whether the secret is set and well-formed, without returning it:
    non-empty, no leading or trailing whitespace, no control character (a
    pasted newline or tab). Nothing else about the value is judged or kept
    (decisions, 20 Nov 2026, secrets pre-flight)."""
    try:
        value = _find(name)
    except ConfigError:
        return "store unavailable"
    if value is None:
        return "not set"
    if value != value.strip() or not value.isprintable():
        return "malformed"
    return "ok"

"""Secrets at run time: env var PO_AGENT_<NAME> first, else keyring service
"po-agent" (CLAUDE.md -> Conventions, Secrets). No other env var is read.
Each site has its own MySys pair (decisions, 10 Nov 2026, live profile); the
live pair is only in poagent's Keychain on the Mac Mini, set by Joey.

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
]
SECRET_NAMES: tuple[str, ...] = get_args(SecretName)
KEYRING_SERVICE = "po-agent"
ENV_PREFIX = "PO_AGENT_"


_MYSYS_NAMES: dict[str, tuple[SecretName, SecretName]] = {
    "test": ("mysys_test_username", "mysys_test_password"),
    "live": ("mysys_live_username", "mysys_live_password"),
}


def mysys_names(site: str) -> tuple[SecretName, SecretName]:
    """The site's MySys (username, password) secret names."""
    if site not in _MYSYS_NAMES:
        raise ValueError("unknown site")
    return _MYSYS_NAMES[site]


def get(name: SecretName) -> str:
    """The secret's value; ConfigError (naming the secret) if it isn't set."""
    if name not in SECRET_NAMES:
        raise ValueError("unknown secret name")
    value = os.environ.get(ENV_PREFIX + name.upper())
    if value:
        return value
    try:
        # Returns None when the entry doesn't exist; backend failures raise
        # KeyringError or a subclass such as NoKeyringError
        # (https://keyring.readthedocs.io/en/latest/, "API" and "Exceptions").
        value = keyring.get_password(KEYRING_SERVICE, name)
    except KeyringError:
        # from None: the backend's message stays out of the error chain.
        raise ConfigError("secret store unavailable", secret=name) from None
    if not value:
        raise ConfigError("secret not set (env var or keyring)", secret=name)
    return value

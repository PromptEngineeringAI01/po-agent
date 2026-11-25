"""Load and validate config/<site>.toml (SPEC.md -> Project Structure) and a
client's config/clients/<client>.toml (task 9.3; SPEC.md -> Client 2, The
separate run): only Summit has one, live only, with its creator table.

Two profiles: config/test.toml and config/live.toml (decisions, 10 Nov 2026,
live profile). Each file's `base_url` must be https on exactly its own site's
host (TEST_HOST or LIVE_HOST, port 443, no user info); live also needs the
live title rule and counts Cancelled tasks as duplicates. Unknown keys are
refused at every level. Any problem is a ConfigError naming the field, never
echoing the value.

LIVE_HOST is the one place the live host is named in src/ (CLAUDE.md Must
never #3). Claude never runs anything against it.
"""

import tomllib
from datetime import time
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from po_agent.core.errors import ConfigError

TEST_HOST = "test-prompt.mysys.com.au"
LIVE_HOST = "prompt.mysys.com.au"
Site = Literal["test", "live"]
SITE_HOSTS: dict[str, str] = {"test": TEST_HOST, "live": LIVE_HOST}
# Each site's Note title rule (b1/decision.py).
SITE_TITLE_RULES: dict[str, str] = {
    "test": "test-body-filename",
    "live": "live-b1-title",
}
CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


class _Section(BaseModel):
    # Config doesn't propagate to nested models, so every model inherits it
    # from here; subclasses merge it with their own
    # (https://docs.pydantic.dev/latest/concepts/config/).
    # extra="forbid": unknown keys raise; frozen=True: no assignment after load
    # (https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict.extra).
    model_config = ConfigDict(extra="forbid", frozen=True)


class RunWindow(_Section):
    days: Literal["Mon-Fri"]
    start: time
    end: time
    tz: str = Field(min_length=1)

    @model_validator(mode="after")
    def _start_before_end(self) -> "RunWindow":
        if self.start >= self.end:
            raise ValueError("start must be before end")
        return self


def _site(info: ValidationInfo) -> str:
    """The already-validated `site` (fields validate in declaration order,
    https://docs.pydantic.dev/latest/concepts/validators/#validation-data);
    missing when `site` itself failed, then every site rule fails too."""
    site = info.data.get("site")
    if site not in SITE_HOSTS:
        raise ValueError("no valid site")
    return site


class Config(_Section):
    site: Site
    base_url: HttpUrl
    pool_name: str = Field(min_length=1)
    agent_user_name: str = Field(min_length=1)
    title_rule: Literal["test-body-filename", "live-b1-title"]
    enabled: StrictBool
    duplicate_ignores_cancelled: StrictBool
    max_notes_per_run: int = Field(gt=0)
    max_run_minutes: int = Field(gt=0)
    run_window: RunWindow
    # Where the stale-Note read (D6) looks: "note_pool" = the Note Pool at
    # All Users (test: one page); "my_notes" = the agent's own My Notes tab
    # (live: 28 pages at All Users, and no agent in the Assigned User list;
    # decisions, 10 Nov 2026, My Notes).
    stale_read: Literal["note_pool", "my_notes"]
    # W2's read-back: the Type of the new task's one row in the project's
    # Documents tab ("Client Documents" on both sites; decisions, 12 Nov 2026).
    project_document_type: str = Field(min_length=1)
    # The safe trace's folder (7.3); "~" is the user's home. Written only
    # when its parent folder exists (core/trace.py).
    trace_dir: str | None = Field(None, min_length=1)

    # https://docs.pydantic.dev/latest/concepts/validators/#field-after-validator
    @field_validator("base_url", mode="after")
    @classmethod
    def _own_host_only(cls, url: HttpUrl, info: ValidationInfo) -> HttpUrl:
        # HttpUrl lowercases the host, so the comparison is exact.
        if (
            url.scheme != "https"
            or url.host != SITE_HOSTS[_site(info)]
            or url.port != 443
            or url.username is not None
            or url.password is not None
        ):
            raise ValueError("base_url must be https on the site's own host")
        return url

    @field_validator("title_rule", mode="after")
    @classmethod
    def _site_title_rule(cls, rule: str, info: ValidationInfo) -> str:
        if rule != SITE_TITLE_RULES[_site(info)]:
            raise ValueError("title_rule is not the site's rule")
        return rule

    @field_validator("duplicate_ignores_cancelled", mode="after")
    @classmethod
    def _live_counts_cancelled(cls, ignores: bool, info: ValidationInfo) -> bool:
        # Only Joey's test-site resets cancel tasks; on live a Cancelled
        # Compaction Test task still counts as a duplicate (SPEC.md).
        if ignores and _site(info) == "live":
            raise ValueError("live counts Cancelled tasks")
        return ignores


def parse_config(data: dict) -> Config:
    try:
        return Config.model_validate(data)
    except ValidationError as error:
        # The field path only: pydantic's text includes the input value.
        loc = error.errors(include_url=False)[0]["loc"]
        field = ".".join(str(part) for part in loc) or None
        raise ConfigError("invalid config value", field=field) from None


def _fold(name: str) -> str:
    """A company name or alias as it is compared: trimmed, case-folded."""
    return name.strip().casefold()


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("blank")
    return value


class Company(_Section):
    """One creator-table row (SPEC.md -> Client 2, Creator table): the row's
    creator, or `previous_task` (the previous task's Task Creator), never
    both."""

    name: str
    aliases: tuple[str, ...] = ()
    creator: str | None = Field(None, min_length=1)
    creator_rule: Literal["previous_task"] | None = None

    @field_validator("name", mode="after")
    @classmethod
    def _name_not_blank(cls, name: str) -> str:
        return _not_blank(name)

    @field_validator("creator", mode="after")
    @classmethod
    def _creator_not_blank(cls, creator: str | None) -> str | None:
        return None if creator is None else _not_blank(creator)

    @field_validator("aliases", mode="after")
    @classmethod
    def _aliases_not_blank(cls, aliases: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_not_blank(alias) for alias in aliases)

    @model_validator(mode="after")
    def _one_creator(self) -> "Company":
        if (self.creator is None) == (self.creator_rule is None):
            raise ValueError("exactly one of creator and creator_rule")
        return self


class ClientProfile(_Section):
    """config/clients/<client>.toml: a client's own values beside the site's
    (SPEC.md -> Client 2, The separate run). Only Summit has one; B1's values
    stay in config/<site>.toml."""

    client: Literal["summit"]
    # Summit has no test-site profile (decisions, 23 Nov 2026).
    sites: tuple[Literal["live"], ...] = Field(min_length=1)
    enabled: StrictBool
    agent_user_name: str = Field(min_length=1)
    source_filter: str = Field(min_length=1)
    sender: str = Field(min_length=1)
    locked_filter: Literal["Unlocked"]
    any_assignee_before: time
    max_notes_per_run: int = Field(gt=0)
    max_peeks_per_run: int = Field(gt=0)
    project_document_type: str = Field(min_length=1)
    company: tuple[Company, ...] = Field(min_length=1)

    @field_validator("company", mode="after")
    @classmethod
    def _names_unique(cls, companies: tuple[Company, ...]) -> tuple[Company, ...]:
        # Every name and alias names one row only, so a company maps to at
        # most one creator.
        seen: set[str] = set()
        for company in companies:
            for name in (company.name, *company.aliases):
                if _fold(name) in seen:
                    raise ValueError("a company name or alias appears twice")
                seen.add(_fold(name))
        return companies


CLIENT_FILES = ("summit",)


def parse_client(data: dict) -> ClientProfile:
    try:
        return ClientProfile.model_validate(data)
    except ValidationError as error:
        # The field path only: pydantic's text includes the input value.
        loc = error.errors(include_url=False)[0]["loc"]
        field = ".".join(str(part) for part in loc) or None
        raise ConfigError("invalid client config value", field=field) from None


def load_client(client: str, site: str, config_dir: Path = CONFIG_DIR) -> ClientProfile:
    """config/clients/<client>.toml; a client without a file is refused
    before any file is opened, and the file must name its own client and
    list the site."""
    if client not in CLIENT_FILES:
        raise ConfigError("client has no client file")
    try:
        with open(config_dir / "clients" / f"{client}.toml", "rb") as file:
            data = tomllib.load(file)
    except OSError:
        raise ConfigError("client file not readable") from None
    except tomllib.TOMLDecodeError:
        raise ConfigError("client file is not valid TOML") from None
    profile = parse_client(data)
    if profile.client != client:
        raise ConfigError("client file is for another client", field="client")
    if site not in profile.sites:
        raise ConfigError("client does not run on that site", field="sites")
    return profile


def load_config(site: str, config_dir: Path = CONFIG_DIR) -> Config:
    """config/<site>.toml for site "test" or "live"; any other site is
    refused before a file is opened, and the file must name its own site."""
    if site not in SITE_HOSTS:
        raise ConfigError("unknown site")
    try:
        with open(config_dir / f"{site}.toml", "rb") as file:
            data = tomllib.load(file)
    except OSError:
        raise ConfigError("config file not readable") from None
    except tomllib.TOMLDecodeError:
        raise ConfigError("config file is not valid TOML") from None
    config = parse_config(data)
    if config.site != site:
        raise ConfigError("config file is for another site", field="site")
    return config

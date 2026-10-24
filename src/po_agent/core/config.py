"""Load and validate config/<site>.toml (SPEC.md -> Project Structure).

The MVP runs on the test site only: `site` must be "test" and `base_url` must
be https on exactly TEST_HOST. Unknown keys are refused at every level. Any
problem is a ConfigError naming the field, never echoing the value.
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
    field_validator,
    model_validator,
)

from po_agent.core.errors import ConfigError

TEST_HOST = "test-prompt.mysys.com.au"
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


class ClaudePrices(_Section):
    input: float = Field(ge=0)
    output: float = Field(ge=0)


class Config(_Section):
    site: Literal["test"]
    base_url: HttpUrl
    pool_name: str = Field(min_length=1)
    agent_user_name: str = Field(min_length=1)
    title_rule: Literal["test-body-filename"]
    reader_mode: Literal["hybrid", "deterministic-only"]
    enabled: StrictBool
    claude_model_id: str = Field(min_length=1)
    duplicate_ignores_cancelled: StrictBool
    max_notes_per_run: int = Field(gt=0)
    max_run_minutes: int = Field(gt=0)
    run_window: RunWindow
    aud_per_usd: float = Field(gt=0)
    claude_price_usd_per_mtok: ClaudePrices

    # https://docs.pydantic.dev/latest/concepts/validators/#field-after-validator
    @field_validator("base_url", mode="after")
    @classmethod
    def _test_host_only(cls, url: HttpUrl) -> HttpUrl:
        # HttpUrl lowercases the host, so the comparison is exact.
        if (
            url.scheme != "https"
            or url.host != TEST_HOST
            or url.port != 443
            or url.username is not None
            or url.password is not None
        ):
            raise ValueError("base_url must be https on the test host")
        return url


def parse_config(data: dict) -> Config:
    try:
        return Config.model_validate(data)
    except ValidationError as error:
        # The field path only: pydantic's text includes the input value.
        loc = error.errors(include_url=False)[0]["loc"]
        field = ".".join(str(part) for part in loc) or None
        raise ConfigError("invalid config value", field=field) from None


def load_config(site: str, config_dir: Path = CONFIG_DIR) -> Config:
    if site != "test":
        raise ConfigError("only the test site is supported")
    try:
        with open(config_dir / "test.toml", "rb") as file:
            data = tomllib.load(file)
    except OSError:
        raise ConfigError("config file not readable") from None
    except tomllib.TOMLDecodeError:
        raise ConfigError("config file is not valid TOML") from None
    return parse_config(data)

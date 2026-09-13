"""Local runtime configuration with safe handling for secret values."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from the process environment and local .env."""

    browserbase_api_key: str | None
    browserbase_project_id: str | None
    browserbase_api_base_url: str
    browserbase_session_timeout_seconds: int
    browser_use_api_key: str | None = None
    browser_use_model: str = "bu-2-0"
    browser_use_base_url: str | None = None

    @classmethod
    def load(
        cls,
        root: Path | None = None,
        *,
        require_browserbase: bool = False,
        require_browser_use: bool = False,
    ) -> Settings:
        project_root = root or Path.cwd()
        load_dotenv(project_root / ".env", override=False)

        settings = cls(
            browserbase_api_key=os.getenv("BROWSERBASE_API_KEY") or None,
            browserbase_project_id=os.getenv("BROWSERBASE_PROJECT_ID") or None,
            browserbase_api_base_url=(
                os.getenv("BROWSERBASE_API_BASE_URL") or "https://api.browserbase.com"
            ).rstrip("/"),
            browserbase_session_timeout_seconds=_int_env(
                "BROWSERBASE_SESSION_TIMEOUT_SECONDS", default=900
            ),
            browser_use_api_key=os.getenv("BROWSER_USE_API_KEY") or None,
            browser_use_model=os.getenv("BROWSER_USE_MODEL") or "bu-2-0",
            browser_use_base_url=os.getenv("BROWSER_USE_BASE_URL") or None,
        )
        if require_browserbase and not settings.browserbase_api_key:
            raise ConfigurationError(
                "BROWSERBASE_API_KEY is not configured; copy .env.example to .env and set it."
            )
        if require_browser_use and not settings.browser_use_api_key:
            raise ConfigurationError(
                "BROWSER_USE_API_KEY is not configured; copy .env.example to .env and set it."
            )
        return settings

    @property
    def browserbase_configured(self) -> bool:
        """Whether the Browserbase API key is available."""

        return bool(self.browserbase_api_key)

    @property
    def masked_browserbase_api_key(self) -> str:
        """Return a display-safe marker without exposing any key material."""

        if not self.browserbase_api_key:
            return "not configured"
        return "configured"

    @property
    def browser_use_configured(self) -> bool:
        """Whether the model provider key for Browser Use is available."""

        return bool(self.browser_use_api_key)

    @property
    def masked_browser_use_api_key(self) -> str:
        """Return a display-safe marker without exposing model key material."""

        return "configured" if self.browser_use_api_key else "not configured"


def _int_env(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error

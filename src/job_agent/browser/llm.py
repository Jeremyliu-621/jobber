"""Model construction for the optional Browser Use agent."""

from __future__ import annotations

from typing import Any

from job_agent.config import ConfigurationError, Settings


def create_browser_llm(settings: Settings | None = None) -> Any:
    """Create the configured Browser Use model without exposing provider details."""

    loaded = settings or Settings.load(require_browser_use=True)
    if not loaded.browser_use_api_key:
        raise ConfigurationError(
            "BROWSER_USE_API_KEY is required to run the model-backed browser agent."
        )
    try:
        from browser_use import ChatBrowserUse  # type: ignore[import-not-found]
    except ImportError as error:  # pragma: no cover - optional runtime path
        raise ConfigurationError(
            "Browser Use is not installed; install the browser extra first."
        ) from error

    kwargs: dict[str, Any] = {
        "model": loaded.browser_use_model,
        "api_key": loaded.browser_use_api_key,
    }
    if loaded.browser_use_base_url:
        kwargs["base_url"] = loaded.browser_use_base_url
    return ChatBrowserUse(**kwargs)

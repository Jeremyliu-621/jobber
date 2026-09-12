"""Provider-neutral browser session interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class BrowserSessionInfo:
    session_id: str
    cdp_url: str
    live_view_url: str | None = None
    profile_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BrowserLiveViewPage:
    """Live URLs for one tab in a running remote browser session."""

    page_id: str
    url: str | None = None
    title: str | None = None
    debugger_url: str | None = None
    debugger_fullscreen_url: str | None = None


@dataclass(frozen=True)
class BrowserLiveView:
    """Provider-neutral live observation URLs for a browser session."""

    session_id: str
    debugger_url: str
    debugger_fullscreen_url: str
    pages: tuple[BrowserLiveViewPage, ...] = ()


@dataclass(frozen=True)
class BrowserReplayPage:
    """Metadata for one recorded browser tab."""

    session_id: str
    page_id: str
    api_path: str
    start_time_ms: int | None = None
    end_time_ms: int | None = None


class BrowserProvider(Protocol):
    async def create_session(
        self,
        *,
        profile_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> BrowserSessionInfo:
        """Create an isolated browser session."""

    async def close_session(self, session_id: str) -> None:
        """Release a browser session."""

    async def get_live_view(self, session_id: str) -> BrowserLiveView:
        """Return live observation URLs for a running browser session."""

    async def list_replays(self, session_id: str) -> tuple[BrowserReplayPage, ...]:
        """List recorded tab replays for a completed or running session."""

    async def get_replay_playlist(self, session_id: str, page_id: str) -> str:
        """Return an HLS playlist without exposing provider credentials."""

"""Browserbase REST provider using the documented Sessions API."""

from __future__ import annotations

from mimetypes import guess_type
from pathlib import Path
from typing import Any

import httpx

from job_agent.config import ConfigurationError, Settings

from .base import BrowserLiveView, BrowserLiveViewPage, BrowserReplayPage, BrowserSessionInfo


class BrowserbaseError(RuntimeError):
    """Raised when Browserbase cannot create or release a session."""


class BrowserbaseProvider:
    name = "browserbase"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or Settings.load(require_browserbase=True)
        if not self.settings.browserbase_api_key:
            raise ConfigurationError("BROWSERBASE_API_KEY is required")
        self._client = client

    async def create_session(
        self,
        *,
        profile_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> BrowserSessionInfo:
        payload: dict[str, Any] = {
            "timeout": max(60, min(self.settings.browserbase_session_timeout_seconds, 21600)),
            "keepAlive": False,
            "userMetadata": metadata or {},
        }
        if self.settings.browserbase_project_id:
            payload["projectId"] = self.settings.browserbase_project_id
        if profile_id:
            payload["browserSettings"] = {"context": {"id": profile_id, "persist": True}}
        response_data = await self._request("POST", "/v1/sessions", json=payload)
        connect_url = response_data.get("connectUrl")
        session_id = response_data.get("id")
        if not connect_url or not session_id:
            raise BrowserbaseError(
                "Browserbase response did not include a session id and connect URL"
            )
        return BrowserSessionInfo(
            session_id=str(session_id),
            cdp_url=str(connect_url),
            live_view_url=None,
            profile_id=profile_id,
            metadata={str(key): str(value) for key, value in (metadata or {}).items()},
        )

    async def close_session(self, session_id: str) -> None:
        payload: dict[str, Any] = {"status": "REQUEST_RELEASE"}
        if self.settings.browserbase_project_id:
            payload["projectId"] = self.settings.browserbase_project_id
        await self._request("POST", f"/v1/sessions/{session_id}", json=payload)

    async def get_live_view(self, session_id: str) -> BrowserLiveView:
        """Fetch signed live-view URLs for a running Browserbase session."""

        data = await self._request("GET", f"/v1/sessions/{session_id}/debug")
        debugger_url = _required_string(data, "debuggerUrl")
        debugger_fullscreen_url = _required_string(data, "debuggerFullscreenUrl")
        pages: list[BrowserLiveViewPage] = []
        raw_pages = data.get("pages", [])
        if isinstance(raw_pages, list):
            for raw_page in raw_pages:
                if not isinstance(raw_page, dict) or not raw_page.get("id"):
                    continue
                pages.append(
                    BrowserLiveViewPage(
                        page_id=str(raw_page["id"]),
                        url=_optional_string(raw_page.get("url")),
                        title=_optional_string(raw_page.get("title")),
                        debugger_url=_optional_string(raw_page.get("debuggerUrl")),
                        debugger_fullscreen_url=_optional_string(
                            raw_page.get("debuggerFullscreenUrl")
                        ),
                    )
                )
        return BrowserLiveView(
            session_id=session_id,
            debugger_url=debugger_url,
            debugger_fullscreen_url=debugger_fullscreen_url,
            pages=tuple(pages),
        )

    async def list_replays(self, session_id: str) -> tuple[BrowserReplayPage, ...]:
        """List the recorded HLS playlist for each Browserbase tab."""

        data = await self._request("GET", f"/v1/sessions/{session_id}/replays")
        raw_pages = data.get("pages", [])
        if not isinstance(raw_pages, list):
            raise BrowserbaseError("Browserbase replay metadata did not include a pages list")
        pages: list[BrowserReplayPage] = []
        for raw_page in raw_pages:
            if not isinstance(raw_page, dict) or raw_page.get("pageId") is None:
                continue
            page_id = str(raw_page["pageId"])
            api_path = _optional_string(raw_page.get("url"))
            if not api_path:
                api_path = f"/v1/sessions/{session_id}/replays/{page_id}"
            pages.append(
                BrowserReplayPage(
                    session_id=session_id,
                    page_id=page_id,
                    api_path=api_path,
                    start_time_ms=_optional_int(raw_page.get("startTimeMs")),
                    end_time_ms=_optional_int(raw_page.get("endTimeMs")),
                )
            )
        return tuple(pages)

    async def get_replay_playlist(self, session_id: str, page_id: str) -> str:
        """Fetch one HLS manifest using the server-side Browserbase key."""

        return await self._request_text("GET", f"/v1/sessions/{session_id}/replays/{page_id}")

    async def upload_file(self, session_id: str, local_path: Path) -> str:
        """Upload a local file and return its session-local Browserbase path."""

        path = Path(local_path)
        if not path.is_file():
            raise BrowserbaseError(f"Upload file does not exist: {path}")
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=self.settings.browserbase_api_base_url,
            timeout=60,
        )
        headers = {"X-BB-API-Key": self.settings.browserbase_api_key or ""}
        content_type = guess_type(path.name)[0] or "application/octet-stream"
        try:
            with path.open("rb") as file_handle:
                response = await client.post(
                    f"/v1/sessions/{session_id}/uploads",
                    headers=headers,
                    files={"file": (path.name, file_handle, content_type)},
                )
                response.raise_for_status()
                data = response.json()
        except (OSError, httpx.HTTPError, ValueError) as error:
            raise BrowserbaseError(
                f"Browserbase upload failed for {path.name}: {error}"
            ) from error
        finally:
            if close_client:
                await client.aclose()
        if not isinstance(data, dict):
            raise BrowserbaseError("Browserbase upload returned a non-object response")
        return f"/tmp/.uploads/{path.name}"

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=self.settings.browserbase_api_base_url,
            timeout=30,
        )
        headers = {"X-BB-API-Key": self.settings.browserbase_api_key or ""}
        try:
            response = await client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise BrowserbaseError(f"Browserbase {method} {path} failed: {error}") from error
        finally:
            if close_client:
                await client.aclose()
        if not isinstance(data, dict):
            raise BrowserbaseError(f"Browserbase {method} {path} returned a non-object response")
        return data

    async def _request_text(self, method: str, path: str, **kwargs: Any) -> str:
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(
            base_url=self.settings.browserbase_api_base_url,
            timeout=30,
        )
        headers = {"X-BB-API-Key": self.settings.browserbase_api_key or ""}
        try:
            response = await client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as error:
            raise BrowserbaseError(f"Browserbase {method} {path} failed: {error}") from error
        finally:
            if close_client:
                await client.aclose()


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise BrowserbaseError(f"Browserbase response did not include {key}")
    return value


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None

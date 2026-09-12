"""Deterministic public job-discovery adapters."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

import httpx
from pydantic import HttpUrl, TypeAdapter

from .models import RawJob


class DiscoveryError(RuntimeError):
    """Raised when a public source cannot be fetched or parsed."""


class JobSource(ABC):
    source_name: str

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def fetch_jobs(self) -> list[RawJob]:
        close_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=30, follow_redirects=True)
        try:
            response = await client.get(self.url)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise DiscoveryError(f"{self.source_name} fetch failed: {error}") from error
        finally:
            if close_client:
                await client.aclose()
        return self.parse_payload(payload)

    @property
    @abstractmethod
    def url(self) -> str:
        """Return the public board endpoint."""

    @abstractmethod
    def parse_payload(self, payload: Any) -> list[RawJob]:
        """Parse a source-specific response into normalized raw jobs."""


class GreenhouseSource(JobSource):
    source_name = "greenhouse"

    def __init__(self, board_token: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client)
        self.board_token = board_token

    @property
    def url(self) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs?content=true"

    def parse_payload(self, payload: Any) -> list[RawJob]:
        rows = payload.get("jobs", []) if isinstance(payload, dict) else []
        return [
            RawJob(
                source=self.source_name,
                source_job_id=str(row["id"]),
                company=str(row.get("company_name") or self.board_token),
                title=str(row.get("title") or "Untitled role"),
                location=_nested_name(row.get("location")),
                url=_url(
                    row.get("absolute_url")
                    or f"https://boards.greenhouse.io/{self.board_token}/jobs/{row['id']}"
                ),
                apply_url=_optional_url(row.get("absolute_url")),
                description_text=html_to_text(str(row.get("content") or "")),
                posted_at=parse_datetime(row.get("updated_at")),
                raw_payload=row,
            )
            for row in rows
            if isinstance(row, dict) and row.get("id")
        ]


class LeverSource(JobSource):
    source_name = "lever"

    def __init__(self, site: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client)
        self.site = site

    @property
    def url(self) -> str:
        return f"https://api.lever.co/v0/postings/{self.site}?mode=json"

    def parse_payload(self, payload: Any) -> list[RawJob]:
        rows = payload if isinstance(payload, list) else []
        return [
            RawJob(
                source=self.source_name,
                source_job_id=str(row["id"]),
                company=self.site,
                title=str(row.get("text") or "Untitled role"),
                location=_lever_location(row),
                url=_url(row.get("hostedUrl") or row.get("applyUrl")),
                apply_url=_url(row.get("applyUrl") or row.get("hostedUrl")),
                description_text=_lever_description(row),
                posted_at=parse_epoch_millis(row.get("createdAt")),
                raw_payload=row,
            )
            for row in rows
            if isinstance(row, dict)
            and row.get("id")
            and (row.get("hostedUrl") or row.get("applyUrl"))
        ]


class AshbySource(JobSource):
    source_name = "ashby"

    def __init__(self, board_name: str, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(client)
        self.board_name = board_name

    @property
    def url(self) -> str:
        return f"https://api.ashbyhq.com/posting-api/job-board/{self.board_name}"

    def parse_payload(self, payload: Any) -> list[RawJob]:
        rows = payload.get("jobs", []) if isinstance(payload, dict) else []
        return [
            RawJob(
                source=self.source_name,
                source_job_id=str(row.get("jobUrl") or row.get("applyUrl")),
                company=self.board_name,
                title=str(row.get("title") or "Untitled role"),
                location=_ashby_location(row),
                url=_url(row.get("jobUrl") or row.get("applyUrl")),
                apply_url=_url(row.get("applyUrl") or row.get("jobUrl")),
                description_text=html_to_text(
                    str(row.get("descriptionHtml") or row.get("description") or "")
                ),
                posted_at=parse_datetime(row.get("publishedAt")),
                raw_payload=row,
            )
            for row in rows
            if isinstance(row, dict) and (row.get("jobUrl") or row.get("applyUrl"))
        ]


class SimplifyJobsSource(JobSource):
    """Read the public SimplifyJobs feeds used by the ``swelist`` CLI.

    Swelist's public CLI returns human-oriented Rich text and does not expose a
    typed Python client.  Reading its underlying public JSON feeds keeps this
    adapter deterministic while preserving the useful source metadata for the
    rest of the application.
    """

    # Keep the persisted source key stable for the 68 records already imported
    # through the original Swelist-facing integration.
    source_name = "swelist"
    canonical_name = "simplifyjobs"
    _FEED_URLS = {
        "internship": (
            "https://raw.githubusercontent.com/SimplifyJobs/"
            "Summer2025-Internships/refs/heads/dev/.github/scripts/listings.json"
        ),
        "newgrad": (
            "https://raw.githubusercontent.com/SimplifyJobs/"
            "New-Grad-Positions/refs/heads/dev/.github/scripts/listings.json"
        ),
    }
    _TIMEFRAME_SECONDS = {
        "lastday": 60 * 60 * 24,
        "lastweek": 60 * 60 * 24 * 7,
        "lastmonth": 60 * 60 * 24 * 30,
    }

    def __init__(
        self,
        role: str = "internship",
        timeframe: str = "lastday",
        location: str = "all",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(client)
        self.role = role.casefold().strip()
        self.timeframe = timeframe.casefold().strip()
        self.location = location.strip() or "all"
        if self.role not in self._FEED_URLS:
            raise ValueError("Swelist role must be internship or newgrad")
        if self.timeframe not in self._TIMEFRAME_SECONDS:
            raise ValueError("Swelist timeframe must be lastday, lastweek, or lastmonth")

    @property
    def url(self) -> str:
        return self._FEED_URLS[self.role]

    def parse_payload(self, payload: Any) -> list[RawJob]:
        if not isinstance(payload, list):
            raise DiscoveryError("Swelist feed returned a non-list payload")

        now = datetime.now(UTC).timestamp()
        threshold = self._TIMEFRAME_SECONDS[self.timeframe]
        results: list[RawJob] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            posted_timestamp = _swelist_timestamp(row.get("date_posted"))
            if posted_timestamp is None or abs(posted_timestamp - now) >= threshold:
                continue
            if not _swelist_location_matches(row, self.location):
                continue

            link = row.get("url")
            if not link:
                continue
            locations = _swelist_locations(row)
            location = row.get("location") or ", ".join(locations) or None
            results.append(
                RawJob(
                    source=self.source_name,
                    source_job_id=str(row.get("id") or link),
                    company=str(row.get("company_name") or "Unknown company"),
                    title=str(row.get("title") or "Untitled role"),
                    location=str(location) if location else None,
                    url=_url(link),
                    apply_url=_url(link),
                    description_text=str(row.get("description") or ""),
                    posted_at=datetime.fromtimestamp(posted_timestamp, tz=UTC),
                    raw_payload={
                        **row,
                        "swelist_role": self.role,
                        "swelist_timeframe": self.timeframe,
                        "swelist_location_filter": self.location,
                        "discovery_source": self.canonical_name,
                    },
                )
            )
        return results


# Public compatibility alias for callers that used the first integration name.
SwelistSource = SimplifyJobsSource


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def html_to_text(value: str) -> str:
    parser = _TextParser()
    parser.feed(value)
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    return re.sub(r"\s+([.,!?;:])", r"\1", text)


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_epoch_millis(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC) if value else None
    except (TypeError, ValueError, OverflowError):
        return None


def _swelist_timestamp(value: Any) -> float | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return timestamp if timestamp >= 0 else None


def _swelist_locations(row: dict[str, Any]) -> list[str]:
    values = row.get("locations")
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    location = row.get("location")
    return [str(location).strip()] if location and str(location).strip() else []


def _swelist_location_matches(row: dict[str, Any], location_filter: str) -> bool:
    normalized_filter = location_filter.casefold().strip()
    if normalized_filter == "all":
        return True
    requested = [value.strip().casefold() for value in location_filter.split(",") if value.strip()]
    locations = [value.casefold() for value in _swelist_locations(row)]
    for requested_location in requested:
        for job_location in locations:
            if len(requested_location) == 2:
                if job_location.endswith(requested_location):
                    return True
            elif requested_location in job_location:
                return True
    return False


def _nested_name(value: Any) -> str | None:
    if isinstance(value, dict):
        name = value.get("name")
        return str(name) if name else None
    return str(value) if value else None


def _lever_location(row: dict[str, Any]) -> str | None:
    categories = row.get("categories") or {}
    location = categories.get("location") if isinstance(categories, dict) else None
    return str(location) if location else None


def _lever_description(row: dict[str, Any]) -> str:
    """Keep the structured Lever sections that contain requirements and bonuses."""

    parts: list[str] = []
    for key in ("descriptionPlain", "description", "additionalPlain", "additional"):
        value = row.get(key)
        if value:
            parts.append(html_to_text(str(value)))
    lists = row.get("lists")
    if isinstance(lists, list):
        for section in lists:
            if not isinstance(section, dict):
                continue
            heading = section.get("text")
            content = section.get("content")
            if heading:
                parts.append(str(heading))
            if content:
                parts.append(html_to_text(str(content)))
    return " ".join(part for part in parts if part).strip()


def _ashby_location(row: dict[str, Any]) -> str | None:
    location = row.get("location")
    if location:
        return str(location)
    locations = row.get("secondaryLocations")
    if isinstance(locations, list):
        values = [
            str(item.get("location") if isinstance(item, dict) else item) for item in locations
        ]
        return ", ".join(value for value in values if value)
    return None


def _url(value: Any) -> HttpUrl:
    if not value:
        raise DiscoveryError("Job source returned a job without a URL")
    return TypeAdapter(HttpUrl).validate_python(str(value))


def _optional_url(value: Any) -> HttpUrl | None:
    return _url(value) if value else None

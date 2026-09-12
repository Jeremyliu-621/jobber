"""Normalized discovery records and deterministic job IDs."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from job_agent.models import Job


class RawJob(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    source_job_id: str | None = None
    company: str
    title: str
    location: str | None = None
    url: HttpUrl
    apply_url: HttpUrl | None = None
    description_text: str = ""
    posted_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


def normalize_job(raw: RawJob) -> Job:
    """Turn a source record into an idempotent domain job."""

    identity = "|".join(
        [
            raw.source.casefold().strip(),
            (raw.source_job_id or "").casefold().strip(),
            raw.company.casefold().strip(),
            raw.title.casefold().strip(),
            str(raw.apply_url or raw.url).casefold().strip(),
        ]
    )
    dedupe_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    source_suffix = raw.source_job_id or dedupe_hash[:20]
    safe_suffix = re.sub(r"[^a-z0-9._-]+", "-", source_suffix.casefold()).strip("-")
    if not safe_suffix or len(safe_suffix) > 80:
        safe_suffix = dedupe_hash[:20]
    safe_source = re.sub(r"[^a-z0-9._-]+", "-", raw.source.casefold()).strip("-")
    return Job(
        id=f"job.{safe_source}.{safe_suffix}",
        source=raw.source,
        source_job_id=raw.source_job_id,
        company=raw.company.strip(),
        title=raw.title.strip(),
        location=raw.location.strip() if raw.location else None,
        url=raw.url,
        apply_url=raw.apply_url,
        description_text=raw.description_text.strip(),
        posted_at=raw.posted_at.astimezone(UTC) if raw.posted_at else None,
        dedupe_hash=dedupe_hash,
        raw_payload=raw.raw_payload,
    )

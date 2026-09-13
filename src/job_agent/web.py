"""Small local web surface for the research desk frontend.

The browser view is intentionally a thin read-only adapter over the existing
SQLite database. It does not create a second source of truth or expose any
browser/provider secrets.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

from .browser import BrowserbaseProvider, BrowserProvider
from .config import ConfigurationError, Settings
from .db import ApplicationRecord, Database, JobRepository, OpportunityRepository
from .service import _browser_session_links


def dashboard_snapshot(root: Path | None = None, *, job_limit: int = 100) -> dict[str, Any]:
    """Return the current operational state needed by the frontend."""

    project_root = _project_root(root)
    database = Database(project_root / "data" / "job-agent.sqlite3")
    database.migrate()
    limit = max(1, min(job_limit, 500))

    with database.session() as connection:
        counts = {
            "jobs_total": _scalar(connection, "SELECT COUNT(*) FROM jobs"),
            "evaluated_jobs": _scalar(
                connection, "SELECT COUNT(DISTINCT job_id) FROM job_evaluations"
            ),
            "applications_total": _scalar(connection, "SELECT COUNT(*) FROM applications"),
            "needs_user": _scalar(
                connection,
                "SELECT COUNT(*) FROM applications WHERE status = 'needs_user'",
            ),
            "submitted": _scalar(
                connection,
                "SELECT COUNT(*) FROM applications WHERE status = 'submitted'",
            ),
            "browser_sessions": _scalar(
                connection,
                "SELECT COUNT(*) FROM applications WHERE browser_session_id IS NOT NULL",
            ),
            "feedback_events": _scalar(connection, "SELECT COUNT(*) FROM user_feedback"),
            "candidate_sources": _scalar(
                connection,
                "SELECT COUNT(*) FROM candidate_sources",
            ),
            "known_facts": _scalar(
                connection,
                "SELECT COUNT(*) FROM candidate_sources WHERE source_type = 'fact'",
            ),
            "resumes": _scalar(connection, "SELECT COUNT(*) FROM resumes"),
        }
        status_counts = _group_counts(
            connection, "SELECT status, COUNT(*) FROM jobs GROUP BY status"
        )
        application_counts = _group_counts(
            connection,
            "SELECT status, COUNT(*) FROM applications GROUP BY status",
        )
        source_counts = _group_counts(
            connection, "SELECT source, COUNT(*) FROM jobs GROUP BY source"
        )
        job_rows = connection.execute(
            """
            SELECT
                j.id,
                j.source,
                j.source_job_id,
                j.company,
                j.title,
                j.location,
                j.url,
                j.apply_url,
                j.description_text,
                j.posted_at,
                j.first_seen_at,
                j.last_seen_at,
                j.status,
                e.eligibility_status,
                e.fit_score,
                e.importance_score,
                e.tier,
                e.summary
            FROM jobs j
            LEFT JOIN job_evaluations e ON e.id = (
                SELECT latest.id
                FROM job_evaluations latest
                WHERE latest.job_id = j.id
                ORDER BY latest.created_at DESC
                LIMIT 1
            )
            ORDER BY COALESCE(j.posted_at, j.first_seen_at) DESC, j.company, j.title
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        application_rows = connection.execute(
            """
            SELECT
                a.id,
                a.job_id,
                a.status,
                a.tier,
                a.resume_id,
                a.browser_provider,
                a.browser_session_id,
                a.created_at,
                a.last_updated_at,
                j.company,
                j.title
            FROM applications a
            JOIN jobs j ON j.id = a.job_id
            ORDER BY a.last_updated_at DESC, a.created_at DESC
            LIMIT 100
            """
        ).fetchall()
        candidate_types = _group_counts(
            connection,
            "SELECT source_type, COUNT(*) FROM candidate_sources GROUP BY source_type",
        )
        migration_version = _scalar(
            connection,
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations",
        )
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])

    application_payloads = [_application_row_to_dict(row) for row in application_rows]
    applications_by_job = {
        application["job_id"]: application for application in application_payloads
    }
    job_payloads = []
    for row in job_rows:
        job_payload = _job_row_to_dict(row)
        job_payload["application"] = applications_by_job.get(job_payload["id"])
        job_payloads.append(job_payload)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "stats": counts,
        "job_statuses": status_counts,
        "application_statuses": application_counts,
        "sources": source_counts,
        "jobs": job_payloads,
        "applications": application_payloads,
        "candidate": {"source_types": candidate_types},
        "system": {
            "database_path": str(database.path),
            "migration_version": migration_version,
            "journal_mode": journal_mode,
            "runtime": "Python service / SQLite WAL / stdio MCP",
            "browserbase": _browserbase_state(project_root),
            "submission_policy": "stop_before_submit",
        },
    }


def job_detail(root: Path | None, job_id: str) -> dict[str, Any]:
    """Return one job and its latest evaluation for progressive disclosure."""

    project_root = _project_root(root)
    database = Database(project_root / "data" / "job-agent.sqlite3")
    repository = JobRepository(database)
    job = repository.get(job_id)
    if job is None:
        raise KeyError(job_id)
    evaluation = repository.latest_evaluation(job_id)
    application = _application_for_job(database, job_id)
    opportunity = OpportunityRepository(database).get(job_id)
    return {
        "job": {
            "id": job.id,
            "source": job.source,
            "source_job_id": job.source_job_id,
            "company": job.company,
            "title": job.title,
            "location": job.location,
            "url": str(job.url),
            "apply_url": str(job.apply_url) if job.apply_url else None,
            "description_text": job.description_text,
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            "status": job.status,
            "raw_payload": job.raw_payload,
            "application": _application_record_to_dict(application),
            "opportunity": opportunity.model_dump(mode="json") if opportunity else None,
        },
        "evaluation": (
            {
                "eligibility_status": evaluation.eligibility_status,
                "fit_score": evaluation.fit_score,
                "importance_score": evaluation.importance_score,
                "tier": evaluation.tier,
                "summary": evaluation.summary,
                "created_at": evaluation.created_at,
                "version": evaluation.version,
            }
            if evaluation
            else None
        ),
    }


def application_browser_links(
    root: Path | None,
    application_id: str,
    *,
    provider: BrowserProvider | None = None,
) -> dict[str, Any]:
    """Return safe live/replay metadata for one stored application session."""

    project_root = _project_root(root)
    session_id = _application_session_id(project_root, application_id)
    if session_id is None:
        return {
            "application_id": application_id,
            "session_id": None,
            "session_inspector_url": None,
            "live_view_status": "unavailable",
            "live_view": None,
            "replay_status": "unavailable",
            "replays": [],
        }
    active_provider = provider or BrowserbaseProvider(
        Settings.load(project_root, require_browserbase=True)
    )
    payload = asyncio.run(
        _browser_session_links(active_provider, application_id, session_id)
    )
    for replay in payload["replays"]:
        replay["playlist_url"] = (
            f"/api/applications/{quote(application_id, safe='')}/replays/"
            f"{quote(str(replay['page_id']), safe='')}"
        )
    return payload


def replay_playlist(
    root: Path | None,
    application_id: str,
    page_id: str,
    *,
    provider: BrowserProvider | None = None,
) -> str:
    """Proxy one allow-listed HLS playlist without exposing Browserbase keys."""

    project_root = _project_root(root)
    session_id = _application_session_id(project_root, application_id)
    if session_id is None:
        raise ValueError("Application has no Browserbase session to inspect")
    active_provider = provider or BrowserbaseProvider(
        Settings.load(project_root, require_browserbase=True)
    )
    return asyncio.run(_replay_playlist(active_provider, session_id, page_id))


def run_server(root: Path | None = None, *, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the frontend and local read-only API until interrupted."""

    project_root = _project_root(root)
    frontend_root = project_root / "frontend"
    if not (frontend_root / "index.html").is_file():
        raise FileNotFoundError(f"Frontend entrypoint not found: {frontend_root / 'index.html'}")

    handler = _handler_for(project_root, frontend_root)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Jobber research desk: http://{host}:{server.server_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Jobber research desk.")
    finally:
        server.server_close()


def _handler_for(project_root: Path, frontend_root: Path):
    class ResearchDeskHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(frontend_root), **kwargs)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/dashboard":
                    query = _query(parsed.query)
                    limit = int(query.get("limit", "100"))
                    self._json(dashboard_snapshot(project_root, job_limit=limit))
                    return
                path_parts = [unquote(part) for part in parsed.path.strip("/").split("/")]
                if (
                    len(path_parts) == 4
                    and path_parts[:2] == ["api", "applications"]
                    and path_parts[3] == "browser-links"
                ):
                    self._json(
                        application_browser_links(project_root, path_parts[2])
                    )
                    return
                if (
                    len(path_parts) == 5
                    and path_parts[:2] == ["api", "applications"]
                    and path_parts[3] == "replays"
                ):
                    playlist = replay_playlist(
                        project_root,
                        path_parts[2],
                        path_parts[4],
                    )
                    self._text(playlist, "application/vnd.apple.mpegurl")
                    return
                if parsed.path.startswith("/api/jobs/"):
                    job_id = unquote(parsed.path.removeprefix("/api/jobs/"))
                    self._json(job_detail(project_root, job_id))
                    return
                if parsed.path == "/api/health":
                    self._json({"ok": True, "generated_at": datetime.now(UTC).isoformat()})
                    return
                super().do_GET()
            except (KeyError, ValueError):
                self._json({"error": "resource not found"}, status=404)
            except Exception as error:  # pragma: no cover - defensive boundary
                self._json({"error": str(error)}, status=500)

        def log_message(self, format: str, *args: object) -> None:
            # Keep the local CLI output readable while retaining normal access logs.
            print(f"[web] {format % args}")

        def _json(self, payload: dict[str, Any], *, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _text(self, body: str, content_type: str, *, status: int = 200) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

    return ResearchDeskHandler


def _project_root(root: Path | None) -> Path:
    if root:
        return Path(root)
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() and (cwd / "candidate").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


def _scalar(connection, query: str) -> int:
    return int(connection.execute(query).fetchone()[0])


def _group_counts(connection, query: str) -> dict[str, int]:
    return {str(row[0] or "unknown"): int(row[1]) for row in connection.execute(query).fetchall()}


def _job_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source": row["source"],
        "source_job_id": row["source_job_id"],
        "company": row["company"],
        "title": row["title"],
        "location": row["location"],
        "url": row["url"],
        "apply_url": row["apply_url"],
        "description_text": row["description_text"],
        "posted_at": row["posted_at"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "status": row["status"],
        "eligibility_status": row["eligibility_status"],
        "fit_score": _number(row["fit_score"]),
        "importance_score": _number(row["importance_score"]),
        "tier": row["tier"],
        "summary": row["summary"] or "",
    }


def _application_for_job(database: Database, job_id: str) -> Any:
    with database.session() as connection:
        row = connection.execute(
            "SELECT * FROM applications WHERE job_id = ? ORDER BY created_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
    return _application_record_from_row(row) if row else None


def _application_record_from_row(row: Any) -> ApplicationRecord:
    return ApplicationRecord(
        id=row["id"],
        job_id=row["job_id"],
        status=row["status"],
        tier=row["tier"],
        resume_id=row["resume_id"],
        browser_provider=row["browser_provider"],
        browser_session_id=row["browser_session_id"],
        created_at=row["created_at"],
        last_updated_at=row["last_updated_at"],
    )


def _application_record_to_dict(
    application: ApplicationRecord | None,
) -> dict[str, Any] | None:
    if application is None:
        return None
    return {
        "id": application.id,
        "job_id": application.job_id,
        "status": application.status,
        "tier": application.tier,
        "resume_id": application.resume_id,
        "browser_provider": application.browser_provider,
        "browser_session_id": application.browser_session_id,
        "created_at": application.created_at,
        "last_updated_at": application.last_updated_at,
    }


def _application_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "company": row["company"],
        "title": row["title"],
        "status": row["status"],
        "tier": row["tier"],
        "resume_id": row["resume_id"],
        "browser_provider": row["browser_provider"],
        "browser_session_id": row["browser_session_id"],
        "created_at": row["created_at"],
        "last_updated_at": row["last_updated_at"],
    }


def _application_session_id(root: Path, application_id: str) -> str | None:
    database = Database(root / "data" / "job-agent.sqlite3")
    with database.session() as connection:
        row = connection.execute(
            """
            SELECT browser_provider, browser_session_id
            FROM applications
            WHERE id = ?
            """,
            (application_id,),
        ).fetchone()
    if row is None:
        raise KeyError(application_id)
    if row["browser_provider"] != "browserbase" or not row["browser_session_id"]:
        return None
    return str(row["browser_session_id"])


async def _replay_playlist(
    provider: BrowserProvider,
    session_id: str,
    page_id: str,
) -> str:
    pages = await provider.list_replays(session_id)
    if not any(page.page_id == page_id for page in pages):
        raise KeyError(page_id)
    return await provider.get_replay_playlist(session_id, page_id)


def _number(value: Any) -> float | None:
    return float(value) if value is not None else None


def _query(raw_query: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in raw_query.split("&"):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key] = value
    return result


def _browserbase_state(root: Path) -> str:
    try:
        settings = Settings.load(root, require_browserbase=False)
    except ConfigurationError:
        return "configuration error"
    return "configured" if settings.browserbase_api_key else "not configured"

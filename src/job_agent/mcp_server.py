"""Local stdio MCP server for Hermes and other compatible clients."""

from __future__ import annotations

import importlib
from typing import Any

from .service import JobAgentService


def _server_class() -> Any:
    try:
        return getattr(importlib.import_module("mcp.server"), "MCPServer")  # noqa: B009
    except (ImportError, AttributeError):  # pragma: no cover - MCP SDK 1.x
        return getattr(importlib.import_module("mcp.server.fastmcp"), "FastMCP")  # noqa: B009


mcp = _server_class()("job-agent")


@mcp.tool()
def find_jobs(status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List normalized job opportunities from the local application database."""

    return JobAgentService().list_jobs(status=status, limit=limit)


@mcp.tool()
def discover_simplifyjobs(
    role: str = "internship",
    timeframe: str = "lastday",
    location: str = "all",
) -> dict[str, Any]:
    """Fetch and persist current SimplifyJobs internship or new-grad postings."""

    job_ids = JobAgentService().discover_simplifyjobs(
        role=role,
        timeframe=timeframe,
        location=location,
    )
    return {
        "source": "simplifyjobs",
        "role": role,
        "timeframe": timeframe,
        "location": location,
        "count": len(job_ids),
        "job_ids": job_ids,
    }


@mcp.tool()
def discover_swelist(
    role: str = "internship",
    timeframe: str = "lastday",
    location: str = "all",
) -> dict[str, Any]:
    """Compatibility alias for the canonical SimplifyJobs discovery tool."""

    return discover_simplifyjobs(role=role, timeframe=timeframe, location=location)


@mcp.tool()
def evaluate_job(job_id: str) -> dict[str, Any]:
    """Evaluate eligibility, fit, evidence gaps, importance, and tier."""

    return JobAgentService().evaluate(job_id).model_dump(mode="json")


@mcp.tool()
def prepare_application(job_id: str) -> str:
    """Build a reviewable application packet and stop before browser submission."""

    return JobAgentService().prepare(job_id).markdown


@mcp.tool()
def get_application_status(application_id: str) -> dict[str, Any]:
    """Read the current application state and browser session metadata."""

    return JobAgentService().application_status(application_id).__dict__


@mcp.tool()
def get_browser_session_links(application_id: str) -> dict[str, Any]:
    """Return a live Browserbase URL or durable Session Inspector replay link."""

    return JobAgentService().browser_session_links(application_id)


@mcp.tool()
def approve_submission(application_id: str) -> dict[str, Any]:
    """Record human review approval while final submission remains disabled."""

    application = JobAgentService().approve_submission(application_id)
    return {
        **application.__dict__,
        "submission_enabled": False,
        "message": "Approval recorded; the browser worker still stops before final submission.",
    }


@mcp.tool()
def get_candidate_fact(path: str) -> dict[str, Any] | None:
    """Retrieve one structured candidate fact; unknown facts return null."""

    service = JobAgentService()
    fact = service.evaluator.facts.get(path)
    return {"path": fact.path, "source_id": fact.source_id, "value": fact.value} if fact else None


@mcp.tool()
def search_candidate_knowledge(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search indexed candidate sources without exposing unindexed files."""

    service = JobAgentService()
    results = service.evaluator.sources.search(query, top_k=top_k)
    return [
        {
            "id": result.id,
            "title": result.title,
            "path": result.path,
            "approved": result.approved,
            "snippet": result.snippet,
        }
        for result in results
    ]


@mcp.tool()
def answer_application_question(application_id: str, question: str, answer: str) -> dict[str, Any]:
    """Record a human-provided application answer with provenance metadata."""

    answer_id = JobAgentService().record_user_answer(
        application_id=application_id,
        question=question,
        answer=answer,
    )
    return {"answer_id": answer_id, "status": "user_supplied"}


@mcp.tool()
def record_feedback(
    artifact_type: str,
    artifact_id: str,
    original_text: str,
    edited_text: str,
    feedback_type: str,
    application_id: str | None = None,
) -> dict[str, Any]:
    """Store an explicit human edit or rejection for later learning reports."""

    feedback_id = JobAgentService().record_feedback(
        application_id=application_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        original_text=original_text,
        edited_text=edited_text,
        feedback_type=feedback_type,
    )
    return {"feedback_id": feedback_id, "status": "recorded"}


@mcp.tool()
def learning_report() -> dict[str, Any]:
    """Summarize human edits and feedback captured by the system."""

    return JobAgentService().learning_report().as_dict()


@mcp.tool()
def health() -> dict[str, Any]:
    """Return a non-secret local service health snapshot."""

    service = JobAgentService()
    status = service.database.status()
    return {"ok": True, "database": status}


def main() -> None:
    """Run the MCP server over stdio."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

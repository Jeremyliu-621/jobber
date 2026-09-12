"""Application service shared by the CLI and Hermes MCP interface."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from job_agent.browser import BrowserbaseProvider, BrowserProvider
from job_agent.candidate import CandidateIndexer
from job_agent.config import Settings
from job_agent.db import ApplicationRecord, ApplicationRepository, Database, JobRepository
from job_agent.discovery import RawJob, SimplifyJobsSource, normalize_job
from job_agent.learning import LearningReport, build_learning_report
from job_agent.models import JobEvaluation
from job_agent.planner import ApplicationPlanner, PreparedPacket
from job_agent.scoring import JobEvaluator


class JobAgentService:
    """Small synchronous facade over the domain modules."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or _default_project_root())
        self.database = Database(self.root / "data" / "job-agent.sqlite3")
        CandidateIndexer(
            candidate_root=self.root / "candidate",
            project_root=self.root,
            database=self.database,
        ).index()
        self.jobs = JobRepository(self.database)
        self.applications = ApplicationRepository(self.database)
        self.evaluator = JobEvaluator(project_root=self.root, database=self.database)
        self.planner = ApplicationPlanner(project_root=self.root, database=self.database)

    def ingest(self, raw_jobs: list[RawJob]) -> list[str]:
        normalized = [normalize_job(raw_job) for raw_job in raw_jobs]
        for job in normalized:
            self.jobs.upsert(job)
        return [job.id for job in normalized]

    def discover_simplifyjobs(
        self,
        *,
        role: str = "internship",
        timeframe: str = "lastday",
        location: str = "all",
    ) -> list[str]:
        """Fetch SimplifyJobs' public feed and persist normalized job records."""

        raw_jobs = asyncio.run(
            SimplifyJobsSource(role=role, timeframe=timeframe, location=location).fetch_jobs()
        )
        return self.ingest(raw_jobs)

    def discover_swelist(
        self,
        *,
        role: str = "internship",
        timeframe: str = "lastday",
        location: str = "all",
    ) -> list[str]:
        """Compatibility alias for the original Swelist-facing service method."""

        return self.discover_simplifyjobs(
            role=role,
            timeframe=timeframe,
            location=location,
        )

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        return [
            {
                "id": job.id,
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "url": str(job.url),
                "status": job.status,
            }
            for job in self.jobs.list_jobs(status=status, limit=limit)
        ]

    def evaluate(self, job_id: str) -> JobEvaluation:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError(f"Unknown job: {job_id}")
        return self.evaluator.persist(job)

    def prepare(self, job_id: str) -> PreparedPacket:
        return self.planner.prepare(job_id)

    def application_status(self, application_id: str) -> ApplicationRecord:
        application = self.applications.get(application_id)
        if application is None:
            raise ValueError(f"Unknown application: {application_id}")
        return application

    def browser_session_links(self, application_id: str) -> dict[str, Any]:
        """Return safe live/replay links for an application's Browserbase session."""

        application = self.application_status(application_id)
        if application.browser_provider != "browserbase" or not application.browser_session_id:
            raise ValueError("Application has no Browserbase session to inspect")
        settings = Settings.load(self.root, require_browserbase=True)
        provider = BrowserbaseProvider(settings)
        return asyncio.run(
            _browser_session_links(provider, application_id, application.browser_session_id)
        )

    def approve_submission(self, application_id: str) -> ApplicationRecord:
        self.application_status(application_id)
        self.applications.update_status(application_id, "ready_to_submit")
        self.applications.add_event(
            application_id,
            "human_approved",
            {"submission_enabled": False, "policy": "stop_before_submit"},
        )
        return self.application_status(application_id)

    def record_user_answer(
        self,
        *,
        application_id: str,
        question: str,
        answer: str,
    ) -> str:
        self.application_status(application_id)
        question_record = self.applications.create_question(
            application_id=application_id,
            question_text=question,
        )
        answer_id = self.applications.save_answer(
            question_id=question_record.id,
            generated_text=None,
            final_text=answer,
            status="user_supplied",
            grounding_score=1.0,
            style_score=1.0,
        )
        self.applications.add_event(
            application_id,
            "user_answered",
            {"question_id": question_record.id, "answer_id": answer_id},
        )
        return answer_id

    def record_feedback(
        self,
        *,
        application_id: str | None,
        artifact_type: str,
        artifact_id: str,
        original_text: str,
        edited_text: str,
        feedback_type: str,
    ) -> str:
        return self.applications.add_feedback(
            application_id=application_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            original_text=original_text,
            edited_text=edited_text,
            feedback_type=feedback_type,
        )

    def learning_report(self) -> LearningReport:
        return build_learning_report(self.database)


def _default_project_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists() and (cwd / "candidate").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


async def _browser_session_links(
    provider: BrowserProvider,
    application_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Fetch current live URLs and replay metadata without returning secrets."""

    live_view: dict[str, Any] | None = None
    live_view_status = "unavailable"
    try:
        live = await provider.get_live_view(session_id)
        live_view_status = "active"
        live_view = {
            "debugger_url": live.debugger_url,
            "debugger_fullscreen_url": live.debugger_fullscreen_url,
            "pages": [
                {
                    "page_id": page.page_id,
                    "url": page.url,
                    "title": page.title,
                    "debugger_url": page.debugger_url,
                    "debugger_fullscreen_url": page.debugger_fullscreen_url,
                }
                for page in live.pages
            ],
        }
    except Exception:
        # A completed session has no live URL; replay retrieval remains useful.
        pass
    replay_status = "unavailable"
    try:
        replay_pages = await provider.list_replays(session_id)
        replay_status = "available"
    except Exception:
        # Recording finalization can lag session release; the inspector URL is
        # still useful while Browserbase finishes processing the recording.
        replay_pages = ()
    return {
        "application_id": application_id,
        "session_id": session_id,
        "session_inspector_url": f"https://www.browserbase.com/sessions/{session_id}",
        "live_view_status": live_view_status,
        "live_view": live_view,
        "replay_status": replay_status,
        "replays": [
            {
                "page_id": page.page_id,
                "start_time_ms": page.start_time_ms,
                "end_time_ms": page.end_time_ms,
            }
            for page in replay_pages
        ],
    }

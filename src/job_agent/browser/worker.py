"""Controlled Browser Use worker boundary.

The worker owns session lifecycle and policy enforcement. A Browser Use runner
is injected so the package remains testable without requiring a model key or a
browser-use installation during planning and evaluation.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from job_agent.db import ApplicationRepository, Database
from job_agent.models import ApplicationPlan

from .base import (
    BrowserProvider,
    HumanEscalationHandler,
    HumanEscalationRequired,
    HumanQuestion,
)
from .policy import build_browser_task


class BrowserRunner(Protocol):
    async def run(
        self,
        *,
        task: str,
            cdp_url: str,
            max_steps: int,
            available_file_paths: list[str] | None = None,
            application_id: str | None = None,
            human_escalation: HumanEscalationHandler | None = None,
        ) -> str:
        """Run a Browser Use task and return a redacted result summary."""


@dataclass(frozen=True)
class BrowserRunResult:
    status: str
    application_id: str
    session_id: str | None
    summary: str
    submitted: bool = False
    live_view_url: str | None = None


class ControlledBrowserWorker:
    def __init__(
        self,
        *,
        provider: BrowserProvider,
        database: Database,
        runner: BrowserRunner | None = None,
    ) -> None:
        self.provider = provider
        self.database = database
        self.applications = ApplicationRepository(database)
        self.runner = runner

    async def run(
        self,
        *,
        plan: ApplicationPlan,
        apply_url: str,
        profile_id: str | None = None,
        max_steps: int = 40,
        human_escalation: HumanEscalationHandler | None = None,
    ) -> BrowserRunResult:
        if plan.importance.tier == "skip":
            return BrowserRunResult(
                "skipped",
                plan.application_id,
                None,
                "Application is below the configured threshold.",
            )
        if plan.eligibility.status != "pass":
            return BrowserRunResult(
                "needs_user", plan.application_id, None, "Eligibility requires user input."
            )
        if not plan.resume:
            return BrowserRunResult(
                "needs_user", plan.application_id, None, "No approved resume is registered."
            )
        if not plan.quality or not plan.quality.passed:
            return BrowserRunResult(
                "needs_user",
                plan.application_id,
                None,
                "Application quality gate has not passed; review the packet before browser work.",
            )
        if self.runner is None:
            return BrowserRunResult(
                "runner_unconfigured",
                plan.application_id,
                None,
                "Browser Use runner is not configured.",
            )

        session = await self.provider.create_session(
            profile_id=profile_id,
            metadata={"application_id": plan.application_id, "tier": plan.importance.tier},
        )
        self.applications.attach_browser_session(
            plan.application_id,
            provider="browserbase",
            session_id=session.session_id,
        )
        self.applications.update_status(plan.application_id, "preparing")
        self.applications.add_event(
            plan.application_id,
            "browser_started",
            {
                "session_id": session.session_id,
                "session_inspector_url": (
                    f"https://www.browserbase.com/sessions/{session.session_id}"
                    if getattr(self.provider, "name", None) == "browserbase"
                    else None
                ),
            },
        )
        live_view_url = session.live_view_url
        try:
            get_live_view = getattr(self.provider, "get_live_view", None)
            if callable(get_live_view):
                try:
                    live_view = await get_live_view(session.session_id)
                    live_view_url = live_view.debugger_fullscreen_url
                    self.applications.add_event(
                        plan.application_id,
                        "browser_live_view",
                        {
                            "session_id": session.session_id,
                            "available": True,
                            "page_ids": [page.page_id for page in live_view.pages],
                        },
                    )
                except Exception as error:
                    self.applications.add_event(
                        plan.application_id,
                        "browser_live_view_error",
                        {
                            "error_type": type(error).__name__,
                            "message": _safe_error_message(error),
                        },
                    )
            local_resume_paths = self._available_resume_paths(plan)
            available_files = local_resume_paths
            upload_file = getattr(self.provider, "upload_file", None)
            if upload_file and available_files:
                available_files = [
                    await upload_file(session.session_id, Path(path)) for path in available_files
                ]
                self.applications.add_event(
                    plan.application_id,
                    "resume_uploaded",
                    {
                        "resume_id": plan.resume.resume_id,
                        "file_name": Path(local_resume_paths[0]).name,
                    },
                )
            summary = await self.runner.run(
                task=build_browser_task(plan, apply_url=apply_url),
                cdp_url=session.cdp_url,
                max_steps=max_steps,
                available_file_paths=available_files,
                application_id=plan.application_id,
                human_escalation=self._human_escalation_handler(
                    plan.application_id, human_escalation
                ),
            )
            self.applications.update_status(plan.application_id, "ready_to_submit")
            self.applications.add_event(
                plan.application_id, "ready_to_submit", {"summary": summary}
            )
            return BrowserRunResult(
                "ready_to_submit",
                plan.application_id,
                session.session_id,
                summary,
                live_view_url=live_view_url,
            )
        except HumanEscalationRequired as error:
            self.applications.update_status(plan.application_id, "needs_user")
            self.applications.add_event(
                plan.application_id,
                "browser_paused_for_user",
                {
                    "question": error.question.question,
                    "context": error.question.context,
                    "allowed_options": list(error.question.allowed_options),
                },
            )
            return BrowserRunResult(
                "needs_user",
                plan.application_id,
                session.session_id,
                f"Human input required: {error.question.question}",
                live_view_url=live_view_url,
            )
        except Exception as error:
            self.applications.update_status(plan.application_id, "failed")
            self.applications.add_event(
                plan.application_id,
                "browser_error",
                {
                    "error_type": type(error).__name__,
                    "message": _safe_error_message(error),
                },
            )
            return BrowserRunResult(
                "failed",
                plan.application_id,
                session.session_id,
                "Browser worker failed; inspect application events.",
            )
        finally:
            try:
                await self.provider.close_session(session.session_id)
            except Exception as error:
                self.applications.add_event(
                    plan.application_id,
                    "browser_release_error",
                    {
                        "error_type": type(error).__name__,
                        "message": _safe_error_message(error),
                    },
                )
            list_replays = getattr(self.provider, "list_replays", None)
            if callable(list_replays):
                try:
                    replay_pages = await list_replays(session.session_id)
                    payload = {
                        "session_id": session.session_id,
                        "pages": [
                            {
                                "page_id": page.page_id,
                                "start_time_ms": page.start_time_ms,
                                "end_time_ms": page.end_time_ms,
                            }
                            for page in replay_pages
                        ],
                    }
                    if getattr(self.provider, "name", None) == "browserbase":
                        payload["session_inspector_url"] = (
                            f"https://www.browserbase.com/sessions/{session.session_id}"
                        )
                    self.applications.add_event(
                        plan.application_id, "browser_replay_available", payload
                    )
                except Exception as error:
                    self.applications.add_event(
                        plan.application_id,
                        "browser_replay_error",
                        {
                            "error_type": type(error).__name__,
                            "message": _safe_error_message(error),
                        },
                    )

    def _human_escalation_handler(
        self,
        application_id: str,
        handler: HumanEscalationHandler | None,
    ) -> HumanEscalationHandler:
        async def handle(question: HumanQuestion) -> str | None:
            question_record = self.applications.create_question(
                application_id=application_id,
                question_text=question.question,
                question_type="human_escalation",
                required=True,
                source_page=question.context[:500] or None,
            )
            self.applications.update_status(application_id, "needs_user")
            self.applications.add_event(
                application_id,
                "human_escalation_requested",
                {
                    "question_id": question_record.id,
                    "context": question.context,
                    "allowed_options": list(question.allowed_options),
                },
            )
            if handler is None:
                return None
            try:
                answer = handler(question)
                if inspect.isawaitable(answer):
                    answer = await answer
            except Exception as error:
                self.applications.add_event(
                    application_id,
                    "human_escalation_error",
                    {
                        "error_type": type(error).__name__,
                        "message": _safe_error_message(error),
                    },
                )
                return None
            if answer is None or not str(answer).strip():
                return None
            answer_id = self.applications.save_answer(
                question_id=question_record.id,
                generated_text=None,
                final_text=str(answer),
                status="user_supplied",
                grounding_score=1.0,
                style_score=1.0,
            )
            self.applications.update_status(application_id, "preparing")
            self.applications.add_event(
                application_id,
                "user_answered",
                {"question_id": question_record.id, "answer_id": answer_id},
            )
            return str(answer)

        return handle

    def _available_resume_paths(self, plan: ApplicationPlan) -> list[str]:
        """Expose only the selected, rendered resume to a Browser Use runner."""

        if not plan.resume:
            return []
        record = next(
            (
                resume
                for resume in self.applications.resumes()
                if resume.id == plan.resume.resume_id
            ),
            None,
        )
        if record is None:
            return []
        path_value = record.rendered_path or record.source_path
        path = Path(path_value)
        if path.is_absolute():
            return [str(path)] if path.is_file() else []
        roots = (self.database.path.parent.parent, self.database.path.parent)
        for root in roots:
            candidate = root / path
            if candidate.is_file():
                return [str(candidate)]
        return []


def _safe_error_message(error: Exception) -> str:
    """Keep provider/model credentials out of the append-only event log."""

    message = str(error)[:500]
    return re.sub(r"(?:bb_live_|sk-)[A-Za-z0-9_-]+", "[REDACTED]", message)

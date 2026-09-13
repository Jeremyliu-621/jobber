"""Persistence for application plans, browser events, and learning feedback."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from job_agent.models import ApplicationQuestion

from .connection import Database


@dataclass(frozen=True)
class ApplicationRecord:
    id: str
    job_id: str
    status: str
    tier: str
    resume_id: str | None
    browser_provider: str | None
    browser_session_id: str | None
    created_at: str
    last_updated_at: str


@dataclass(frozen=True)
class ResumeRecord:
    id: str
    name: str
    base_type: str
    source_path: str
    rendered_path: str | None
    version: str


@dataclass(frozen=True)
class ApplicationAnswerRecord:
    id: str
    question_id: str
    question_text: str
    final_text: str
    status: str


class ApplicationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        job_id: str,
        tier: str,
        status: str,
        resume_id: str | None = None,
    ) -> str:
        self.database.migrate()
        application_id = f"application.{uuid.uuid4().hex}"
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO applications(id, job_id, status, tier, resume_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (application_id, job_id, status, tier, resume_id),
            )
        return application_id

    def get(self, application_id: str) -> ApplicationRecord | None:
        self.database.migrate()
        with self.database.session() as connection:
            row = connection.execute(
                "SELECT * FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
        return self._application_from_row(row) if row else None

    def find_for_job(self, job_id: str) -> ApplicationRecord | None:
        self.database.migrate()
        with self.database.session() as connection:
            row = connection.execute(
                """
                SELECT * FROM applications
                WHERE job_id = ? ORDER BY created_at DESC LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        return self._application_from_row(row) if row else None

    def update_status(self, application_id: str, status: str) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                """
                UPDATE applications
                SET status = ?, last_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, application_id),
            )

    def update_plan(
        self,
        application_id: str,
        *,
        tier: str,
        status: str,
        resume_id: str | None,
    ) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                """
                UPDATE applications
                SET tier = ?, status = ?, resume_id = ?, last_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (tier, status, resume_id, application_id),
            )

    def attach_browser_session(
        self,
        application_id: str,
        *,
        provider: str,
        session_id: str,
    ) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                """
                UPDATE applications
                SET browser_provider = ?, browser_session_id = ?,
                    started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (provider, session_id, application_id),
            )

    def add_question(self, question: ApplicationQuestion) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO application_questions(
                    id, application_id, question_text, normalized_question,
                    question_type, required, max_length, source_page
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question.id,
                    question.application_id,
                    question.question_text,
                    question.normalized_question,
                    question.question_type,
                    int(question.required),
                    question.max_length,
                    question.source_page,
                ),
            )

    def create_question(
        self,
        *,
        application_id: str,
        question_text: str,
        question_type: str = "free_response",
        required: bool = False,
        max_length: int | None = None,
        source_page: str | None = None,
    ) -> ApplicationQuestion:
        question = ApplicationQuestion(
            id=f"question.{uuid.uuid4().hex}",
            application_id=application_id,
            question_text=question_text,
            normalized_question=" ".join(question_text.casefold().split()),
            question_type=question_type,
            required=required,
            max_length=max_length,
            source_page=source_page,
        )
        self.add_question(question)
        return question

    def save_answer(
        self,
        *,
        question_id: str,
        generated_text: str | None,
        final_text: str | None,
        status: str,
        grounding_score: float | None = None,
        style_score: float | None = None,
        human_edit_distance: float | None = None,
    ) -> str:
        self.database.migrate()
        answer_id = f"answer.{uuid.uuid4().hex}"
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO application_answers(
                    id, question_id, generated_text, final_text, status,
                    grounding_score, style_score, human_edit_distance, approved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    answer_id,
                    question_id,
                    generated_text,
                    final_text,
                    status,
                    grounding_score,
                    style_score,
                    human_edit_distance,
                    datetime.now(UTC).isoformat() if status == "approved" else None,
                ),
            )
        return answer_id

    def answers(self, application_id: str) -> list[ApplicationAnswerRecord]:
        """Return human-usable answers already recorded for an application."""

        self.database.migrate()
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT a.id, a.question_id, q.question_text, a.final_text, a.status
                FROM application_answers a
                JOIN application_questions q ON q.id = a.question_id
                WHERE q.application_id = ? AND a.final_text IS NOT NULL
                ORDER BY a.created_at
                """,
                (application_id,),
            ).fetchall()
        return [
            ApplicationAnswerRecord(
                id=row["id"],
                question_id=row["question_id"],
                question_text=row["question_text"],
                final_text=row["final_text"],
                status=row["status"],
            )
            for row in rows
        ]

    def add_event(
        self,
        application_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        self.database.migrate()
        event_id = f"event.{uuid.uuid4().hex}"
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO application_events(id, application_id, event_type, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, application_id, event_type, json.dumps(payload or {})),
            )
        return event_id

    def add_feedback(
        self,
        *,
        application_id: str | None,
        artifact_type: str,
        artifact_id: str,
        original_text: str,
        edited_text: str,
        feedback_type: str,
    ) -> str:
        self.database.migrate()
        feedback_id = f"feedback.{uuid.uuid4().hex}"
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO user_feedback(
                    id, application_id, artifact_type, artifact_id,
                    original_text, edited_text, feedback_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    application_id,
                    artifact_type,
                    artifact_id,
                    original_text,
                    edited_text,
                    feedback_type,
                ),
            )
        return feedback_id

    def resumes(self) -> list[ResumeRecord]:
        self.database.migrate()
        with self.database.session() as connection:
            rows = connection.execute("SELECT * FROM resumes ORDER BY name").fetchall()
        return [
            ResumeRecord(
                id=row["id"],
                name=row["name"],
                base_type=row["base_type"],
                source_path=row["source_path"],
                rendered_path=row["rendered_path"],
                version=row["version"],
            )
            for row in rows
        ]

    def upsert_resume(self, resume: ResumeRecord) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO resumes(id, name, base_type, source_path, rendered_path, version)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    base_type=excluded.base_type,
                    source_path=excluded.source_path,
                    rendered_path=excluded.rendered_path,
                    version=excluded.version
                """,
                (
                    resume.id,
                    resume.name,
                    resume.base_type,
                    resume.source_path,
                    resume.rendered_path,
                    resume.version,
                ),
            )

    @staticmethod
    def _application_from_row(row: Any) -> ApplicationRecord:
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

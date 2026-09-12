"""Persistence for normalized jobs, criteria, and evaluations."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from job_agent.models import Job, JobCriterion, JobEvaluation

from .connection import Database


@dataclass(frozen=True)
class JobEvaluationRecord:
    id: str
    job_id: str
    eligibility_status: str
    fit_score: float
    importance_score: float
    tier: str
    summary: str
    created_at: str
    version: str


class JobRepository:
    """Read and write normalized jobs without exposing raw SQLite rows."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, job: Job) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO jobs(
                    id, source, source_job_id, company, title, location, url, apply_url,
                    description_text, posted_at, status, dedupe_hash, raw_payload_json,
                    last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    source=excluded.source,
                    source_job_id=excluded.source_job_id,
                    company=excluded.company,
                    title=excluded.title,
                    location=excluded.location,
                    url=excluded.url,
                    apply_url=excluded.apply_url,
                    description_text=excluded.description_text,
                    posted_at=excluded.posted_at,
                    status=excluded.status,
                    dedupe_hash=excluded.dedupe_hash,
                    raw_payload_json=excluded.raw_payload_json,
                    last_seen_at=CURRENT_TIMESTAMP
                """,
                (
                    job.id,
                    job.source,
                    job.source_job_id,
                    job.company,
                    job.title,
                    job.location,
                    str(job.url),
                    str(job.apply_url) if job.apply_url else None,
                    job.description_text,
                    job.posted_at.isoformat() if job.posted_at else None,
                    job.status,
                    job.dedupe_hash,
                    json.dumps(job.raw_payload),
                ),
            )

    def get(self, job_id: str) -> Job | None:
        self.database.migrate()
        with self.database.session() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_from_row(row) if row else None

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[Job]:
        self.database.migrate()
        limit = max(1, min(limit, 500))
        with self.database.session() as connection:
            if status:
                rows = connection.execute(
                    """
                    SELECT * FROM jobs WHERE status = ?
                    ORDER BY COALESCE(posted_at, first_seen_at) DESC LIMIT ?
                    """,
                    (status, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM jobs
                    ORDER BY COALESCE(posted_at, first_seen_at) DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def save_criteria(self, job_id: str, criteria: list[JobCriterion]) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute("DELETE FROM job_criteria WHERE job_id = ?", (job_id,))
            connection.executemany(
                """
                INSERT INTO job_criteria(id, job_id, name, category, weight, source_text)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        criterion.id,
                        job_id,
                        criterion.name,
                        criterion.category,
                        criterion.weight,
                        criterion.source_text,
                    )
                    for criterion in criteria
                ],
            )

    def criteria(self, job_id: str) -> list[JobCriterion]:
        self.database.migrate()
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT * FROM job_criteria WHERE job_id = ? ORDER BY weight DESC, name",
                (job_id,),
            ).fetchall()
        return [
            JobCriterion(
                id=row["id"],
                job_id=row["job_id"],
                name=row["name"],
                category=row["category"],
                weight=row["weight"],
                source_text=row["source_text"],
            )
            for row in rows
        ]

    def save_evaluation(self, evaluation: JobEvaluation) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO job_evaluations(
                    id, job_id, eligibility_status, fit_score, importance_score,
                    tier, summary, model_id, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    eligibility_status=excluded.eligibility_status,
                    fit_score=excluded.fit_score,
                    importance_score=excluded.importance_score,
                    tier=excluded.tier,
                    summary=excluded.summary,
                    model_id=excluded.model_id,
                    version=excluded.version
                """,
                (
                    evaluation.id,
                    evaluation.job_id,
                    evaluation.eligibility.status,
                    evaluation.fit.score,
                    evaluation.importance.score,
                    evaluation.importance.tier,
                    evaluation.summary,
                    "deterministic-v1",
                    evaluation.version,
                ),
            )

    def save_evidence(self, evidence: dict[str, list[Any]]) -> None:
        """Persist the inspectable criterion-to-candidate-source matrix."""

        self.database.migrate()
        criterion_ids = tuple(evidence)
        with self.database.session() as connection:
            if criterion_ids:
                placeholders = ",".join("?" for _ in criterion_ids)
                connection.execute(
                    f"DELETE FROM criterion_evidence WHERE criterion_id IN ({placeholders})",
                    criterion_ids,
                )
            rows = []
            for criterion_id, items in evidence.items():
                for item in items:
                    evidence_id = "evidence.{}".format(
                        hashlib.sha256(
                            f"{criterion_id}:{item.source_id}".encode()
                        ).hexdigest()[:20]
                    )
                    rows.append(
                        (
                            evidence_id,
                            criterion_id,
                            item.source_id,
                            item.strength,
                            item.notes,
                        )
                    )
            connection.executemany(
                """
                INSERT INTO criterion_evidence(
                    id, criterion_id, candidate_source_id, strength, notes
                ) VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )

    def update_status(self, job_id: str, status: str) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, last_seen_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, job_id),
            )

    def latest_evaluation(self, job_id: str) -> JobEvaluationRecord | None:
        self.database.migrate()
        with self.database.session() as connection:
            row = connection.execute(
                """
                SELECT * FROM job_evaluations
                WHERE job_id = ? ORDER BY created_at DESC LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return JobEvaluationRecord(
            id=row["id"],
            job_id=row["job_id"],
            eligibility_status=row["eligibility_status"],
            fit_score=float(row["fit_score"] or 0),
            importance_score=float(row["importance_score"] or 0),
            tier=row["tier"] or "skip",
            summary=row["summary"],
            created_at=row["created_at"],
            version=row["version"],
        )

    @staticmethod
    def _job_from_row(row: Any) -> Job:
        posted_at = datetime.fromisoformat(row["posted_at"]) if row["posted_at"] else None
        return Job(
            id=row["id"],
            source=row["source"],
            source_job_id=row["source_job_id"],
            company=row["company"],
            title=row["title"],
            location=row["location"],
            url=row["url"],
            apply_url=row["apply_url"],
            description_text=row["description_text"],
            posted_at=posted_at,
            status=row["status"],
            dedupe_hash=row["dedupe_hash"],
            raw_payload=json.loads(row["raw_payload_json"] or "{}"),
        )


def new_evaluation_id(job_id: str) -> str:
    return f"evaluation.{job_id}.{uuid.uuid4().hex[:12]}"

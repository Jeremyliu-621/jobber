"""Aggregate reversible feedback without mutating hard candidate facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from job_agent.db import Database


@dataclass(frozen=True)
class LearningReport:
    feedback_count: int
    edited_count: int
    edit_rate: float
    feedback_by_type: dict[str, int]
    application_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "feedback_count": self.feedback_count,
            "edited_count": self.edited_count,
            "edit_rate": self.edit_rate,
            "feedback_by_type": self.feedback_by_type,
            "application_count": self.application_count,
        }


def build_learning_report(database: Database) -> LearningReport:
    database.migrate()
    with database.session() as connection:
        feedback_count = int(connection.execute("SELECT COUNT(*) FROM user_feedback").fetchone()[0])
        edited_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM user_feedback WHERE original_text <> edited_text"
            ).fetchone()[0]
        )
        rows = connection.execute(
            """
            SELECT feedback_type, COUNT(*) AS count
            FROM user_feedback GROUP BY feedback_type ORDER BY feedback_type
            """
        ).fetchall()
        application_count = int(
            connection.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        )
    return LearningReport(
        feedback_count=feedback_count,
        edited_count=edited_count,
        edit_rate=edited_count / feedback_count if feedback_count else 0.0,
        feedback_by_type={row["feedback_type"]: int(row["count"]) for row in rows},
        application_count=application_count,
    )

from pathlib import Path

from job_agent.db import ApplicationRepository, Database, JobRepository
from job_agent.discovery.models import RawJob, normalize_job


def test_approved_answer_records_a_real_timestamp(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.sqlite3")
    job = normalize_job(
        RawJob(
            source="test",
            source_job_id="answer-1",
            company="Acme",
            title="Software Engineer",
            url="https://example.com/jobs/answer-1",
        )
    )
    JobRepository(database).upsert(job)
    applications = ApplicationRepository(database)
    application_id = applications.create(job_id=job.id, tier="tier_c", status="ready_for_review")
    question = applications.create_question(
        application_id=application_id,
        question_text="Why this company?",
    )

    answer_id = applications.save_answer(
        question_id=question.id,
        generated_text=None,
        final_text="User supplied answer.",
        status="approved",
    )

    with database.session() as connection:
        row = connection.execute(
            "SELECT approved_at FROM application_answers WHERE id = ?",
            (answer_id,),
        ).fetchone()
    assert row["approved_at"]
    assert row["approved_at"] != "CURRENT_TIMESTAMP"

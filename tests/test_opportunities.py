from pathlib import Path

from job_agent.db import Database, JobRepository, OpportunityRepository
from job_agent.models import Job
from job_agent.opportunities import extract_opportunity


def _job(description: str, raw_payload: dict | None = None) -> Job:
    return Job(
        id="job.test.opportunity",
        source="ashby",
        source_job_id="opportunity-1",
        company="Example Labs",
        title="Software Engineer Intern",
        location="Toronto, Canada",
        url="https://example.com/jobs/opportunity-1",
        description_text=description,
        dedupe_hash="opportunity-1",
        raw_payload=raw_payload or {},
    )


def test_extractor_preserves_html_sections_and_lists() -> None:
    job = _job(
        "Who We Are Example Labs. What You'll Achieve Build systems. Qualifications Python.",
        {
            "descriptionHtml": (
                "<h1>Who We Are</h1><p>Example Labs builds tools.</p>"
                "<h2>What You'll Achieve:</h2><ul><li>Build systems.</li>"
                "<li>Ship tested code.</li></ul>"
                "<h2>Qualifications</h2><p>Python experience.</p>"
            )
        },
    )

    opportunity = extract_opportunity(job)

    assert [section.key for section in opportunity.sections] == [
        "company",
        "work",
        "qualifications",
    ]
    assert opportunity.sections[1].kind == "list"
    assert opportunity.sections[1].items == ["Build systems.", "Ship tested code."]
    assert opportunity.sections[2].items == ["Python experience."]


def test_plain_extractor_does_not_split_prose_into_fake_headings() -> None:
    opportunity = extract_opportunity(
        _job(
            "About the Role: Build useful systems. Qualifications: Python required. "
            "A Note on AI You do not need deep AI expertise, but qualifications may change. "
            "Equal opportunity employer."
        )
    )

    assert [section.key for section in opportunity.sections] == [
        "role",
        "qualifications",
        "details",
    ]
    assert opportunity.sections[1].items == ["Python required."]
    assert any("Equal opportunity employer." in item for item in opportunity.sections[2].items)


def test_opportunity_repository_round_trips_source_hash_and_sections(tmp_path: Path) -> None:
    database = Database(tmp_path / "data.sqlite3")
    database.migrate()
    job = _job("Qualifications: Python required.")
    JobRepository(database).upsert(job)
    opportunity = extract_opportunity(job)
    repository = OpportunityRepository(database)

    repository.upsert(opportunity)
    stored = repository.get(opportunity.job_id)

    assert stored == opportunity
    assert repository.count() == 1

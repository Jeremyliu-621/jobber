from pathlib import Path

from job_agent.candidate import CandidateIndexer
from job_agent.db import Database
from job_agent.discovery.models import RawJob, normalize_job
from job_agent.models import Job
from job_agent.scoring import JobEvaluator


def _project_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "candidate" / "projects").mkdir(parents=True)
    (root / "candidate" / "profile.yaml").write_text(
        """
identity:
  email: person@example.com
education:
  - institution: Example University
    graduation_date: 2027-05-01
work_authorization:
  canada:
    authorized: true
    sponsorship_required: false
preferences:
  target_roles: [Software Engineer]
  locations: [Toronto]
  remote: true
""",
        encoding="utf-8",
    )
    (root / "candidate" / "preferences.yaml").write_text("{}\n", encoding="utf-8")
    (root / "candidate" / "projects" / "api.md").write_text(
        """---
id: project.api
type: project
approved: true
source: user-authored
topics: [python, sql]
---
Built a Python service backed by PostgreSQL and wrote unit tests.
""",
        encoding="utf-8",
    )
    return root


def test_evaluator_produces_inspectable_fit_and_eligibility(tmp_path: Path) -> None:
    root = _project_root(tmp_path)
    database = Database(root / "data.sqlite3")
    CandidateIndexer(
        candidate_root=root / "candidate", project_root=root, database=database
    ).index()
    job = normalize_job(
        RawJob(
            source="test",
            source_job_id="job-1",
            company="Acme",
            title="Software Engineer",
            location="Toronto, Canada",
            url="https://example.com/jobs/1",
            description_text="Qualifications: Python and SQL required. Docker is a plus.",
        )
    )

    evaluation = JobEvaluator(project_root=root, database=database).persist(job)

    assert evaluation.eligibility.status == "pass"
    assert evaluation.fit.score > 50
    assert {criterion.name for criterion in evaluation.fit.criteria} >= {"python", "sql", "docker"}
    assert "python" not in evaluation.fit.gaps
    assert evaluation.importance.tier in {"tier_c", "tier_b", "tier_a"}


def test_unknown_authorization_is_uncertain(tmp_path: Path) -> None:
    root = _project_root(tmp_path)
    profile = root / "candidate" / "profile.yaml"
    profile_text = profile.read_text(encoding="utf-8")
    profile_text = profile_text.replace(
        "  canada:\n    authorized: true", "  canada:\n    authorized:"
    )
    profile_text = profile_text.replace(
        "    sponsorship_required: false", "    sponsorship_required:"
    )
    profile.write_text(profile_text, encoding="utf-8")
    database = Database(root / "data.sqlite3")
    CandidateIndexer(
        candidate_root=root / "candidate", project_root=root, database=database
    ).index()
    job = Job(
        id="job.test.auth",
        source="test",
        source_job_id="auth",
        company="Acme",
        title="Software Engineer",
        location="Toronto, Canada",
        url="https://example.com/jobs/auth",
        dedupe_hash="auth",
    )
    evaluation = JobEvaluator(project_root=root, database=database).evaluate(job)
    assert evaluation.eligibility.status == "uncertain"
    assert "work_authorization.canada.authorized" in evaluation.eligibility.missing_facts


def test_us_city_and_state_location_requires_us_authorization(tmp_path: Path) -> None:
    root = _project_root(tmp_path)
    profile = root / "candidate" / "profile.yaml"
    profile_text = profile.read_text(encoding="utf-8")
    profile.write_text(
        profile_text.replace(
            "work_authorization:\n  canada:",
            "work_authorization:\n  usa:\n    authorized:\n    sponsorship_required:\n  canada:",
        ),
        encoding="utf-8",
    )
    database = Database(root / "data.sqlite3")
    CandidateIndexer(
        candidate_root=root / "candidate", project_root=root, database=database
    ).index()
    job = Job(
        id="job.test.us-location",
        source="test",
        source_job_id="us-location",
        company="Acme",
        title="Software Engineer Intern",
        location="Peachtree Corners, GA",
        url="https://example.com/jobs/us-location",
        dedupe_hash="us-location",
    )

    evaluation = JobEvaluator(project_root=root, database=database).evaluate(job)

    assert evaluation.eligibility.status == "uncertain"
    assert "work_authorization.usa.authorized" in evaluation.eligibility.missing_facts

from pathlib import Path

from job_agent.db import ApplicationRepository, Database, JobRepository, ResumeRecord
from job_agent.discovery.models import RawJob, normalize_job
from job_agent.planner import ApplicationPlanner


def test_prepare_creates_reviewable_packet_without_submission(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "candidate").mkdir(parents=True)
    (root / "candidate" / "resumes").mkdir()
    (root / "candidate" / "profile.yaml").write_text(
        "preferences:\n  target_roles: [Software Engineer]\n", encoding="utf-8"
    )
    (root / "candidate" / "preferences.yaml").write_text("{}\n", encoding="utf-8")
    database = Database(root / "data.sqlite3")
    job = normalize_job(
        RawJob(
            source="test",
            source_job_id="packet-1",
            company="Acme",
            title="Software Engineer",
            url="https://example.com/jobs/packet-1",
            description_text="Build software with Python.",
        )
    )
    JobRepository(database).upsert(job)

    ApplicationRepository(database).upsert_resume(
        ResumeRecord(
            id="resume-1",
            name="Backend resume",
            base_type="python",
            source_path="candidate/resumes/backend.pdf",
            rendered_path=None,
            version="1",
        )
    )
    (root / "candidate" / "resumes" / "backend.pdf").write_bytes(b"%PDF-test")

    planner = ApplicationPlanner(project_root=root, database=database)
    packet = planner.prepare(job.id)
    repeated = planner.prepare(job.id)

    assert packet.plan.application_id.startswith("application.")
    assert repeated.plan.application_id == packet.plan.application_id
    assert packet.plan.resume is not None
    assert (
        ApplicationRepository(database).get(packet.plan.application_id).resume_id == "resume-1"
    )
    assert packet.plan.quality is not None
    assert packet.plan.quality.passed is True
    assert "Final submission is disabled" in packet.markdown


def test_prepare_requires_rendered_pdf_for_latex_source(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "candidate" / "resumes").mkdir(parents=True)
    (root / "candidate" / "profile.yaml").write_text(
        "preferences:\n  target_roles: [Software Engineer]\n", encoding="utf-8"
    )
    (root / "candidate" / "preferences.yaml").write_text("{}\n", encoding="utf-8")
    (root / "candidate" / "resumes" / "resume.tex").write_text(
        "\\documentclass{article}\\begin{document}resume\\end{document}",
        encoding="utf-8",
    )
    database = Database(root / "data.sqlite3")
    job = normalize_job(
        RawJob(
            source="test",
            source_job_id="packet-tex",
            company="Acme",
            title="Software Engineer",
            url="https://example.com/jobs/packet-tex",
            description_text="Build software.",
        )
    )
    JobRepository(database).upsert(job)
    ApplicationRepository(database).upsert_resume(
        ResumeRecord(
            id="resume-tex",
            name="LaTeX resume",
            base_type="python",
            source_path="candidate/resumes/resume.tex",
            rendered_path=None,
            version="1",
        )
    )

    packet = ApplicationPlanner(project_root=root, database=database).prepare(job.id)

    assert packet.plan.quality is not None
    assert packet.plan.quality.passed is False
    assert packet.plan.next_action == "register_resume_and_review"
    assert "rendered PDF resume is required" in packet.markdown

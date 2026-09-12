import asyncio
from pathlib import Path

from job_agent.browser import BrowserSessionInfo, ControlledBrowserWorker
from job_agent.db import ApplicationRepository, Database, ResumeRecord
from job_agent.discovery.models import RawJob
from job_agent.service import JobAgentService


def test_review_only_workflow_runs_from_job_to_browser_boundary(tmp_path: Path) -> None:
    root = tmp_path / "project"
    candidate = root / "candidate"
    (candidate / "projects").mkdir(parents=True)
    (candidate / "resumes").mkdir()
    (candidate / "profile.yaml").write_text(
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
    (candidate / "preferences.yaml").write_text("{}\n", encoding="utf-8")
    (candidate / "projects" / "api.md").write_text(
        """---
id: project.api
type: project
approved: true
source: user-authored
topics: [python]
---
Built a Python service and wrote unit tests.
""",
        encoding="utf-8",
    )
    (candidate / "resumes" / "resume.pdf").write_bytes(b"%PDF-test")

    database = Database(root / "data" / "job-agent.sqlite3")
    ApplicationRepository(database).upsert_resume(
        ResumeRecord(
            id="resume-1",
            name="Current resume",
            base_type="python+testing",
            source_path="candidate/resumes/resume.pdf",
            rendered_path=None,
            version="1",
        )
    )
    service = JobAgentService(root)
    job_ids = service.ingest(
        [
            RawJob(
                source="test",
                source_job_id="e2e-1",
                company="Acme",
                title="Software Engineer",
                location="Toronto, Canada",
                url="https://example.com/jobs/e2e-1",
                description_text="Qualifications: Python required. Unit testing is a plus.",
            )
        ]
    )

    evaluation = service.evaluate(job_ids[0])
    packet = service.prepare(job_ids[0])

    assert evaluation.eligibility.status == "pass"
    assert packet.plan.quality is not None and packet.plan.quality.passed is True
    assert packet.plan.resume is not None
    application = ApplicationRepository(database).get(packet.plan.application_id)
    assert application is not None

    class FakeProvider:
        created = False
        closed = False

        async def create_session(self, *, profile_id=None, metadata=None):
            self.created = True
            return BrowserSessionInfo("session-e2e", "wss://example.com/cdp")

        async def close_session(self, session_id: str) -> None:
            self.closed = True

    class FakeRunner:
        async def run(
            self,
            *,
            task: str,
            cdp_url: str,
            max_steps: int,
            available_file_paths: list[str] | None = None,
        ) -> str:
            assert "stop before final submission" in task
            assert "https://example.com/apply" in task
            assert available_file_paths == [str(candidate / "resumes" / "resume.pdf")]
            return "Prepared form and stopped before submission."

    provider = FakeProvider()
    result = asyncio.run(
        ControlledBrowserWorker(
            provider=provider,
            database=database,
            runner=FakeRunner(),
        ).run(plan=packet.plan, apply_url="https://example.com/apply")
    )

    assert result.status == "ready_to_submit"
    assert result.submitted is False
    assert provider.created is True
    assert provider.closed is True

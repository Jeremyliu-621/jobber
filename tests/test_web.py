from pathlib import Path

from job_agent.browser import BrowserLiveView, BrowserLiveViewPage, BrowserReplayPage
from job_agent.db import ApplicationRepository, Database
from job_agent.models import Job
from job_agent.web import (
    application_browser_links,
    dashboard_snapshot,
    job_detail,
    replay_playlist,
)


def test_dashboard_snapshot_is_read_only_and_contains_current_records(tmp_path: Path) -> None:
    root = tmp_path
    database = Database(root / "data" / "job-agent.sqlite3")
    database.migrate()
    job = Job(
        id="job.test.1",
        source="simplifyjobs",
        source_job_id="test-1",
        company="Example Labs",
        title="Software Engineering Intern",
        location="Toronto, ON",
        url="https://example.com/jobs/test-1",
        apply_url="https://example.com/apply/test-1",
        description_text="Build useful systems.",
        dedupe_hash="dedupe-test-1",
    )
    with database.session() as connection:
        connection.execute(
            """
            INSERT INTO jobs(
                id, source, source_job_id, company, title, location, url, apply_url,
                description_text, dedupe_hash, raw_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.source,
                job.source_job_id,
                job.company,
                job.title,
                job.location,
                str(job.url),
                str(job.apply_url),
                job.description_text,
                job.dedupe_hash,
                "{}",
            ),
        )
        connection.execute(
            """
            INSERT INTO job_evaluations(
                id, job_id, eligibility_status, fit_score, importance_score,
                tier, summary, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "evaluation.test.1",
                job.id,
                "pass",
                82.5,
                74.0,
                "tier_b",
                "Strong evidence match.",
                "1",
            ),
        )

    payload = dashboard_snapshot(root)

    assert payload["stats"]["jobs_total"] == 1
    assert payload["stats"]["evaluated_jobs"] == 1
    assert payload["sources"] == {"simplifyjobs": 1}
    assert payload["jobs"][0]["fit_score"] == 82.5
    assert payload["jobs"][0]["tier"] == "tier_b"
    assert payload["system"]["journal_mode"] == "wal"


def test_job_detail_returns_latest_evaluation(tmp_path: Path) -> None:
    root = tmp_path
    database = Database(root / "data" / "job-agent.sqlite3")
    database.migrate()
    with database.session() as connection:
        connection.execute(
            """
            INSERT INTO jobs(
                id, source, source_job_id, company, title, url,
                description_text, dedupe_hash, raw_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job.test.2",
                "ashby",
                "test-2",
                "Research Company",
                "New Grad Engineer",
                "https://example.com/jobs/test-2",
                "",
                "dedupe-test-2",
                '{"team":"platform"}',
            ),
        )

    detail = job_detail(root, "job.test.2")

    assert detail["job"]["company"] == "Research Company"
    assert detail["job"]["raw_payload"] == {"team": "platform"}
    assert detail["job"]["opportunity"] is None
    assert detail["evaluation"] is None


def test_browser_links_proxy_live_view_and_replay_playlist(tmp_path: Path) -> None:
    root = tmp_path
    database = Database(root / "data" / "job-agent.sqlite3")
    database.migrate()
    with database.session() as connection:
        connection.execute(
            """
            INSERT INTO jobs(
                id, source, source_job_id, company, title, url,
                description_text, dedupe_hash, raw_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "job.test.replay",
                "simplifyjobs",
                "replay-1",
                "Replay Labs",
                "Software Engineer",
                "https://example.com/jobs/replay-1",
                "",
                "dedupe-replay-1",
                "{}",
            ),
        )
    applications = ApplicationRepository(database)
    application_id = applications.create(
        job_id="job.test.replay",
        tier="tier_c",
        status="needs_user",
    )
    applications.attach_browser_session(
        application_id,
        provider="browserbase",
        session_id="session.replay",
    )

    class FakeProvider:
        async def get_live_view(self, session_id: str) -> BrowserLiveView:
            assert session_id == "session.replay"
            return BrowserLiveView(
                session_id=session_id,
                debugger_url="https://live.example/debug",
                debugger_fullscreen_url="https://live.example/fullscreen",
                pages=(
                    BrowserLiveViewPage(
                        page_id="page-1",
                        url="https://example.com/apply",
                        title="Apply",
                    ),
                ),
            )

        async def list_replays(self, session_id: str) -> tuple[BrowserReplayPage, ...]:
            assert session_id == "session.replay"
            return (
                BrowserReplayPage(
                    session_id=session_id,
                    page_id="page-1",
                    api_path="/v1/sessions/session.replay/replays/page-1",
                ),
            )

        async def get_replay_playlist(self, session_id: str, page_id: str) -> str:
            assert session_id == "session.replay"
            assert page_id == "page-1"
            return "#EXTM3U\n#EXT-X-ENDLIST\n"

    links = application_browser_links(root, application_id, provider=FakeProvider())

    assert links["live_view_status"] == "active"
    assert links["replay_status"] == "available"
    assert links["replays"][0]["playlist_url"] == (
        f"/api/applications/{application_id}/replays/page-1"
    )
    assert replay_playlist(
        root,
        application_id,
        "page-1",
        provider=FakeProvider(),
    ) == "#EXTM3U\n#EXT-X-ENDLIST\n"

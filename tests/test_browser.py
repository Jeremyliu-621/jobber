import asyncio
import json
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest

from job_agent.browser import (
    BrowserbaseProvider,
    BrowserLiveView,
    BrowserLiveViewPage,
    BrowserReplayPage,
    BrowserSessionInfo,
    BrowserUseRunner,
    ControlledBrowserWorker,
    HumanEscalationRequired,
    HumanQuestion,
    create_browser_llm,
)
from job_agent.config import Settings
from job_agent.db import ApplicationRepository, Database, JobRepository, ResumeRecord
from job_agent.models import (
    ApplicationPlan,
    EligibilityResult,
    FitEvaluation,
    ImportanceEvaluation,
    Job,
    QualityReport,
    ResumeChoice,
)
from job_agent.service import _browser_session_links


def test_browserbase_provider_uses_project_and_context_without_real_session() -> None:
    calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, json.loads(request.content)))
        if request.method == "POST" and request.url.path == "/v1/sessions":
            return httpx.Response(
                201,
                json={"id": "session-1", "connectUrl": "wss://connect.example/session-1"},
            )
        return httpx.Response(200, json={"status": "REQUEST_RELEASE"})

    settings = Settings(
        browserbase_api_key="test-key",
        browserbase_project_id="project-1",
        browserbase_api_base_url="https://api.browserbase.com",
        browserbase_session_timeout_seconds=900,
    )
    provider = BrowserbaseProvider(
        settings,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.browserbase.com",
        ),
    )

    async def exercise() -> None:
        session = await provider.create_session(profile_id="context-1", metadata={"job": "1"})
        await provider.close_session(session.session_id)
        assert session.cdp_url.startswith("wss://")

    asyncio.run(exercise())

    assert calls[0][2]["projectId"] == "project-1"
    assert calls[0][2]["browserSettings"]["context"]["persist"] is True
    assert calls[1][2]["status"] == "REQUEST_RELEASE"


def test_browserbase_provider_uploads_to_session_and_returns_remote_path(tmp_path: Path) -> None:
    calls: list[tuple[str, str, bytes]] = []
    resume = tmp_path / "Jeremy_Liu_Resume.pdf"
    resume.write_bytes(b"%PDF-1.4 test")

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={"message": "uploaded"})

    settings = Settings(
        browserbase_api_key="test-key",
        browserbase_project_id="project-1",
        browserbase_api_base_url="https://api.browserbase.com",
        browserbase_session_timeout_seconds=900,
    )
    provider = BrowserbaseProvider(
        settings,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.browserbase.com",
        ),
    )

    remote_path = asyncio.run(provider.upload_file("session-1", resume))

    assert remote_path == "/tmp/.uploads/Jeremy_Liu_Resume.pdf"
    assert calls[0][0:2] == ("POST", "/v1/sessions/session-1/uploads")
    assert b"Jeremy_Liu_Resume.pdf" in calls[0][2]


def test_browserbase_provider_fetches_live_view_and_replay_metadata() -> None:
    requests: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path.endswith("/debug"):
            return httpx.Response(
                200,
                json={
                    "debuggerUrl": "https://live.example/session-1",
                    "debuggerFullscreenUrl": "https://live.example/full/session-1",
                    "pages": [
                        {
                            "id": "0",
                            "url": "https://example.com",
                            "title": "Example",
                            "debuggerUrl": "https://live.example/session-1/0",
                            "debuggerFullscreenUrl": "https://live.example/full/session-1/0",
                        }
                    ],
                },
            )
        if request.url.path.endswith("/replays"):
            return httpx.Response(
                200,
                json={
                    "pages": [
                        {
                            "pageId": "0",
                            "url": "/v1/sessions/session-1/replays/0",
                            "startTimeMs": 0,
                            "endTimeMs": 1200,
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            content=b"#EXTM3U\nhttps://cdn.example/segment.m4s\n",
            headers={"content-type": "application/vnd.apple.mpegurl"},
        )

    settings = Settings(
        browserbase_api_key="test-key",
        browserbase_project_id="project-1",
        browserbase_api_base_url="https://api.browserbase.com",
        browserbase_session_timeout_seconds=900,
    )
    provider = BrowserbaseProvider(
        settings,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.browserbase.com",
        ),
    )

    async def exercise() -> None:
        live = await provider.get_live_view("session-1")
        replays = await provider.list_replays("session-1")
        playlist = await provider.get_replay_playlist("session-1", "0")
        assert live.debugger_fullscreen_url == "https://live.example/full/session-1"
        assert live.pages[0] == BrowserLiveViewPage(
            page_id="0",
            url="https://example.com",
            title="Example",
            debugger_url="https://live.example/session-1/0",
            debugger_fullscreen_url="https://live.example/full/session-1/0",
        )
        assert replays == (
            BrowserReplayPage(
                session_id="session-1",
                page_id="0",
                api_path="/v1/sessions/session-1/replays/0",
                start_time_ms=0,
                end_time_ms=1200,
            ),
        )
        assert playlist.startswith("#EXTM3U")

    asyncio.run(exercise())
    assert requests == [
        ("GET", "/v1/sessions/session-1/debug"),
        ("GET", "/v1/sessions/session-1/replays"),
        ("GET", "/v1/sessions/session-1/replays/0"),
    ]


def test_browser_session_links_keep_completed_replay_available() -> None:
    class CompletedProvider:
        async def get_live_view(self, session_id: str) -> BrowserLiveView:
            raise RuntimeError("session is no longer running")

        async def list_replays(self, session_id: str) -> tuple[BrowserReplayPage, ...]:
            return (BrowserReplayPage(session_id, "0", "/v1/sessions/session-1/replays/0"),)

        async def get_replay_playlist(self, session_id: str, page_id: str) -> str:
            return "#EXTM3U"

    links = asyncio.run(_browser_session_links(CompletedProvider(), "application-1", "session-1"))

    assert links["live_view_status"] == "unavailable"
    assert links["live_view"] is None
    assert links["session_inspector_url"] == "https://www.browserbase.com/sessions/session-1"
    assert links["replay_status"] == "available"
    assert links["replays"] == [{"page_id": "0", "start_time_ms": None, "end_time_ms": None}]


def test_browser_use_runner_uses_remote_mode_and_stops_on_error(monkeypatch) -> None:
    state: dict[str, object] = {}

    class FakeBrowser:
        def __init__(self, **kwargs):
            state["browser_kwargs"] = kwargs

        async def stop(self) -> None:
            state["stopped"] = True

    class FakeAgent:
        def __init__(self, **kwargs):
            state["agent_kwargs"] = kwargs

        async def run(self, *, max_steps: int):
            raise RuntimeError("runner failed")

    class FakeActionResult:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeTools:
        def __init__(self):
            self.actions = {}

        def action(self, description: str, **kwargs):
            def decorator(function):
                self.actions[function.__name__] = function
                return function

            return decorator

    fake_module = ModuleType("browser_use")
    fake_module.Agent = FakeAgent
    fake_module.Browser = FakeBrowser
    fake_module.ActionResult = FakeActionResult
    fake_module.Tools = FakeTools
    monkeypatch.setitem(sys.modules, "browser_use", fake_module)

    with pytest.raises(RuntimeError, match="runner failed"):
        asyncio.run(
            BrowserUseRunner(object()).run(
                task="read only",
                cdp_url="wss://example/cdp",
                max_steps=2,
                available_file_paths=["C:/resume.pdf"],
            )
        )

    assert state["browser_kwargs"] == {
        "cdp_url": "wss://example/cdp",
        "is_local": False,
        "keep_alive": False,
    }
    assert state["agent_kwargs"]["available_file_paths"] == ["C:/resume.pdf"]
    assert state["stopped"] is True


def test_browser_use_runner_rejects_history_without_final_result(monkeypatch) -> None:
    class FakeBrowser:
        def __init__(self, **kwargs):
            pass

        async def stop(self):
            pass

    class FakeActionResult:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeTools:
        def action(self, description: str, **kwargs):
            def decorator(function):
                return function

            return decorator

    class FakeHistory:
        def final_result(self):
            return None

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

        async def run(self, *, max_steps: int):
            return FakeHistory()

    fake_module = ModuleType("browser_use")
    fake_module.Agent = FakeAgent
    fake_module.Browser = FakeBrowser
    fake_module.ActionResult = FakeActionResult
    fake_module.Tools = FakeTools
    monkeypatch.setitem(sys.modules, "browser_use", fake_module)

    with pytest.raises(RuntimeError, match="did not produce a final result"):
        asyncio.run(
            BrowserUseRunner(object()).run(
                task="prepare the form",
                cdp_url="wss://example/cdp",
                max_steps=2,
            )
        )


def test_worker_stops_before_submission(tmp_path: Path) -> None:
    class FakeProvider:
        created = False
        closed = False
        uploaded: list[tuple[str, Path]] = []

        async def create_session(self, *, profile_id=None, metadata=None):
            self.created = True
            return BrowserSessionInfo("session-1", "wss://connect.example/session-1")

        async def close_session(self, session_id: str) -> None:
            self.closed = True

        async def upload_file(self, session_id: str, local_path: Path) -> str:
            self.uploaded.append((session_id, local_path))
            return "/tmp/.uploads/backend.pdf"

        async def get_live_view(self, session_id: str) -> BrowserLiveView:
            return BrowserLiveView(
                session_id=session_id,
                debugger_url="https://live.example/session-1",
                debugger_fullscreen_url="https://live.example/full/session-1",
            )

        async def list_replays(self, session_id: str) -> tuple[BrowserReplayPage, ...]:
            return (BrowserReplayPage(session_id, "0", "/v1/sessions/session-1/replays/0"),)

    class FakeRunner:
        async def run(
            self,
            *,
            task: str,
            cdp_url: str,
            max_steps: int,
            available_file_paths: list[str] | None = None,
            application_id: str | None = None,
            human_escalation=None,
        ) -> str:
            assert "stop before final submission" in task
            assert available_file_paths == ["/tmp/.uploads/backend.pdf"]
            return "prepared"

    database = Database(tmp_path / "data.sqlite3")
    rendered_resume = tmp_path / "candidate" / "resumes" / "backend.pdf"
    rendered_resume.parent.mkdir(parents=True)
    rendered_resume.write_bytes(b"%PDF-1.4 test")
    JobRepository(database).upsert(
        Job(
            id="job-1",
            source="test",
            company="Acme",
            title="Engineer",
            url="https://example.com/jobs/1",
            dedupe_hash="job-1",
        )
    )
    ApplicationRepository(database).upsert_resume(
        ResumeRecord(
            id="resume-1",
            name="Backend resume",
            base_type="python+sql",
            source_path="candidate/resumes/backend.md",
            rendered_path="candidate/resumes/backend.pdf",
            version="1",
        )
    )
    application_id = ApplicationRepository(database).create(
        job_id="job-1", tier="tier_c", status="ready_for_review", resume_id="resume-1"
    )
    plan = ApplicationPlan(
        application_id=application_id,
        job_id="job-1",
        eligibility=EligibilityResult(status="pass"),
        fit=FitEvaluation(score=80),
        importance=ImportanceEvaluation(score=80, tier="tier_c"),
        resume=ResumeChoice(resume_id="resume-1"),
        quality=QualityReport(passed=True, grounding_score=1.0, style_score=1.0),
    )
    provider = FakeProvider()

    async def exercise():
        return await ControlledBrowserWorker(
            provider=provider,
            database=database,
            runner=FakeRunner(),
        ).run(plan=plan, apply_url="https://example.com/apply")

    result = asyncio.run(exercise())

    assert result.status == "ready_to_submit"
    assert result.submitted is False
    assert provider.created is True
    assert provider.closed is True
    assert provider.uploaded == [("session-1", rendered_resume)]
    assert result.live_view_url == "https://live.example/full/session-1"
    with database.session() as connection:
        event_types = [
            row[0]
            for row in connection.execute(
                "SELECT event_type FROM application_events WHERE application_id = ?",
                (application_id,),
            )
        ]
    assert "browser_live_view" in event_types
    assert "browser_replay_available" in event_types


def test_browser_use_runner_can_pause_for_and_receive_a_human_answer(monkeypatch) -> None:
    state: dict[str, object] = {}

    class FakeBrowser:
        def __init__(self, **kwargs):
            pass

        async def stop(self) -> None:
            pass

    class FakeActionResult:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeTools:
        def __init__(self):
            self.actions = {}

        def action(self, description: str, **kwargs):
            def decorator(function):
                self.actions[function.__name__] = function
                return function

            return decorator

    class FakeHistory:
        def final_result(self):
            return "prepared"

    class FakeAgent:
        def __init__(self, **kwargs):
            state["tools"] = kwargs["tools"]

        async def run(self, *, max_steps: int):
            result = await state["tools"].actions["ask_user"](
                "Are you authorized to work in Canada?",
                "Application asks a work authorization question.",
                ["Yes", "No"],
            )
            state["ask_result"] = result
            return FakeHistory()

    fake_module = ModuleType("browser_use")
    fake_module.Agent = FakeAgent
    fake_module.Browser = FakeBrowser
    fake_module.ActionResult = FakeActionResult
    fake_module.Tools = FakeTools
    monkeypatch.setitem(sys.modules, "browser_use", fake_module)

    asked = []

    async def answer(question):
        asked.append(question)
        return "Yes"

    summary = asyncio.run(
        BrowserUseRunner(object(), human_escalation=answer).run(
            task="prepare the form",
            cdp_url="wss://example/cdp",
            max_steps=2,
            application_id="application-1",
        )
    )

    assert summary == "prepared"
    assert asked[0].application_id == "application-1"
    assert asked[0].allowed_options == ("Yes", "No")
    assert state["ask_result"].kwargs["extracted_content"] == (
        "Human answer (use exactly as provided): Yes"
    )


def test_create_browser_llm_uses_configured_browser_use_model(monkeypatch) -> None:
    state: dict[str, object] = {}

    class FakeChatBrowserUse:
        def __init__(self, **kwargs):
            state["kwargs"] = kwargs

    fake_module = ModuleType("browser_use")
    fake_module.ChatBrowserUse = FakeChatBrowserUse
    monkeypatch.setitem(sys.modules, "browser_use", fake_module)

    llm = create_browser_llm(
        Settings(
            browserbase_api_key=None,
            browserbase_project_id=None,
            browserbase_api_base_url="https://api.browserbase.com",
            browserbase_session_timeout_seconds=900,
            browser_use_api_key="model-key",
            browser_use_model="test-browser-model",
            browser_use_base_url="https://llm.example.com",
        )
    )

    assert isinstance(llm, FakeChatBrowserUse)
    assert state["kwargs"] == {
        "model": "test-browser-model",
        "api_key": "model-key",
        "base_url": "https://llm.example.com",
    }


def test_worker_refuses_failed_quality_gate(tmp_path: Path) -> None:
    class FakeProvider:
        created = False

        async def create_session(self, *, profile_id=None, metadata=None):
            self.created = True
            raise AssertionError("provider must not be called")

        async def close_session(self, session_id: str) -> None:
            raise AssertionError("provider must not be called")

    database = Database(tmp_path / "data.sqlite3")
    application_id = "application.quality-gate"
    plan = ApplicationPlan(
        application_id=application_id,
        job_id="job-1",
        eligibility=EligibilityResult(status="pass"),
        fit=FitEvaluation(score=80),
        importance=ImportanceEvaluation(score=80, tier="tier_c"),
        resume=ResumeChoice(resume_id="resume-1"),
        quality=QualityReport(passed=False, grounding_score=0.5, style_score=1.0),
    )

    async def exercise():
        return await ControlledBrowserWorker(
            provider=FakeProvider(),
            database=database,
            runner=object(),
        ).run(plan=plan, apply_url="https://example.com/apply")

    result = asyncio.run(exercise())

    assert result.status == "needs_user"
    assert "quality gate" in result.summary


def test_worker_records_unanswered_human_escalation(tmp_path: Path) -> None:
    class FakeProvider:
        async def create_session(self, *, profile_id=None, metadata=None):
            return BrowserSessionInfo("session-ask", "wss://connect.example/session-ask")

        async def close_session(self, session_id: str) -> None:
            pass

    class FakeRunner:
        async def run(
            self,
            *,
            task: str,
            cdp_url: str,
            max_steps: int,
            available_file_paths: list[str] | None = None,
            application_id: str | None = None,
            human_escalation=None,
        ) -> str:
            question = HumanQuestion(
                application_id=application_id,
                question="Are you authorized to work in the United States?",
                context="The application asks a required legal question.",
                allowed_options=("Yes", "No"),
            )
            assert human_escalation is not None
            assert await human_escalation(question) is None
            raise HumanEscalationRequired(question)

    database = Database(tmp_path / "data.sqlite3")
    rendered_resume = tmp_path / "candidate" / "resumes" / "backend.pdf"
    rendered_resume.parent.mkdir(parents=True)
    rendered_resume.write_bytes(b"%PDF-1.4 test")
    JobRepository(database).upsert(
        Job(
            id="job-ask",
            source="test",
            company="Acme",
            title="Engineer",
            url="https://example.com/jobs/ask",
            dedupe_hash="job-ask",
        )
    )
    ApplicationRepository(database).upsert_resume(
        ResumeRecord(
            id="resume-ask",
            name="Backend resume",
            base_type="python",
            source_path="candidate/resumes/backend.pdf",
            rendered_path="candidate/resumes/backend.pdf",
            version="1",
        )
    )
    application_id = ApplicationRepository(database).create(
        job_id="job-ask", tier="tier_c", status="ready_for_review", resume_id="resume-ask"
    )
    plan = ApplicationPlan(
        application_id=application_id,
        job_id="job-ask",
        eligibility=EligibilityResult(status="pass"),
        fit=FitEvaluation(score=80),
        importance=ImportanceEvaluation(score=80, tier="tier_c"),
        resume=ResumeChoice(resume_id="resume-ask"),
        quality=QualityReport(passed=True, grounding_score=1.0, style_score=1.0),
    )

    result = asyncio.run(
        ControlledBrowserWorker(
            provider=FakeProvider(),
            database=database,
            runner=FakeRunner(),
        ).run(plan=plan, apply_url="https://example.com/apply")
    )

    assert result.status == "needs_user"
    assert result.submitted is False
    application = ApplicationRepository(database).get(application_id)
    assert application is not None and application.status == "needs_user"
    with database.session() as connection:
        question = connection.execute(
            "SELECT question_text, question_type "
            "FROM application_questions WHERE application_id = ?",
            (application_id,),
        ).fetchone()
        event_types = [
            row[0]
            for row in connection.execute(
                "SELECT event_type FROM application_events WHERE application_id = ?",
                (application_id,),
            )
        ]
    assert question[0] == "Are you authorized to work in the United States?"
    assert question[1] == "human_escalation"
    assert "human_escalation_requested" in event_types
    assert "browser_paused_for_user" in event_types

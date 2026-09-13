"""Typer command-line interface for the first application-system slice."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from .agent_runner import AgentTask, LocalAgentError, LocalCliRunner, available_providers
from .browser import HumanQuestion
from .candidate import CandidateFactStore, CandidateIndexer, load_profile
from .config import ConfigurationError, Settings
from .db import ApplicationRepository, CandidateSourceRepository, Database, ResumeRecord
from .discovery import AshbySource, GreenhouseSource, LeverSource
from .discovery.sources import JobSource
from .documents import import_document, inventory
from .service import JobAgentService
from .workspace import (
    WorkspaceConfigurationError,
    config_path,
    effective_config,
    initialize_workspace,
    resolve_workspace_root,
    update_config,
)

app = typer.Typer(help="Personal SWE job application system.")
candidate_app = typer.Typer(help="Inspect and search the candidate brain.")
db_app = typer.Typer(help="Inspect application state storage.")
config_app = typer.Typer(help="Inspect local runtime configuration.")
job_app = typer.Typer(help="Discover, evaluate, and list jobs.")
application_app = typer.Typer(help="Prepare and inspect applications.")
learning_app = typer.Typer(help="Inspect feedback and learning signals.")
resume_app = typer.Typer(help="Manage the local resume inventory.")
documents_app = typer.Typer(help="Inventory documents in the selected local folder.")
agent_app = typer.Typer(help="Use a locally installed Codex or Claude CLI.")
app.add_typer(candidate_app, name="candidate")
app.add_typer(db_app, name="db")
app.add_typer(config_app, name="config")
app.add_typer(job_app, name="job")
app.add_typer(application_app, name="application")
app.add_typer(learning_app, name="learning")
app.add_typer(resume_app, name="resume")
app.add_typer(documents_app, name="documents")
app.add_typer(agent_app, name="agent")


@app.command("init")
def initialize(
    workspace: Annotated[
        Path | None, typer.Argument(help="Workspace directory to create and select.")
    ] = None,
    no_select: Annotated[
        bool, typer.Option("--no-select", help="Create files without changing user config.")
    ] = False,
) -> None:
    """Create a blank local workspace and select it for future commands."""

    try:
        selected = resolve_workspace_root(workspace) if workspace else None
        created = initialize_workspace(selected, select=not no_select)
    except Exception as error:
        typer.echo(f"INIT FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    root = selected or resolve_workspace_root()
    typer.echo(f"Workspace: {root}")
    typer.echo(f"Created {len(created)} starter files.")
    if not no_select:
        typer.echo(f"Selected in {config_path()}")
    typer.echo("Add verified facts to candidate/profile.yaml and documents to documents/inbox.")


@app.command("web")
def web_server(
    host: Annotated[str, typer.Option("--host", help="Local bind address.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
) -> None:
    """Serve the local research desk frontend over the existing SQLite state."""

    try:
        from .web import run_server

        run_server(_root(), host=host, port=port)
    except Exception as error:
        typer.echo(f"WEB SERVER FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error


def _root() -> Path:
    try:
        return resolve_workspace_root()
    except WorkspaceConfigurationError as error:
        typer.echo(f"WORKSPACE CONFIG FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error


def _database(root: Path | None = None) -> Database:
    base = root or _root()
    return Database(base / "data" / "job-agent.sqlite3")


def _index(root: Path | None = None) -> CandidateIndexer:
    base = root or _root()
    return CandidateIndexer(
        candidate_root=base / "candidate",
        project_root=base,
        database=_database(base),
    )


@candidate_app.command("validate")
def candidate_validate(
    profile: Annotated[
        Path, typer.Option("--profile", help="Structured profile YAML path.")
    ] = Path("candidate/profile.yaml"),
) -> None:
    """Validate structured candidate facts without filling unknown values."""

    try:
        loaded = load_profile(profile)
    except Exception as error:
        typer.echo(f"INVALID: {error}", err=True)
        raise typer.Exit(code=1) from error
    known = len(CandidateFactStore(loaded).all())
    typer.echo(f"VALID: {profile} ({known} known facts)")


@candidate_app.command("index")
def candidate_index() -> None:
    """Index structured facts and candidate Markdown files into SQLite."""

    try:
        count = _index().index()
    except Exception as error:
        typer.echo(f"INDEX FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Indexed {count} candidate sources.")


@candidate_app.command("fact")
def candidate_fact(path: Annotated[str, typer.Argument(help="Dotted fact path.")]) -> None:
    """Retrieve one verified fact; unknown values fail safely."""

    try:
        profile = load_profile(_root() / "candidate" / "profile.yaml")
        fact = CandidateFactStore(profile).get(path)
    except Exception as error:
        typer.echo(f"FACT LOOKUP FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    if fact is None:
        typer.echo(f"UNKNOWN: {path}")
        raise typer.Exit(code=1)
    typer.echo(json.dumps({"path": fact.path, "source_id": fact.source_id, "value": fact.value}))


@candidate_app.command("search")
def candidate_search(
    query: Annotated[str, typer.Argument(help="Search text.")],
    source_type: Annotated[
        list[str] | None,
        typer.Option("--type", help="Restrict results to a candidate source type."),
    ] = None,
    top_k: Annotated[int, typer.Option("--top-k", min=1, max=100)] = 5,
) -> None:
    """Search indexed candidate knowledge."""

    try:
        _index().index()
        repository = CandidateSourceRepository(_database())
        results = repository.search(query, source_types=source_type, top_k=top_k)
    except Exception as error:
        typer.echo(f"SEARCH FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    if not results:
        typer.echo("No matching candidate sources.")
        return
    for result in results:
        approval = "approved" if result.approved else "unapproved"
        typer.echo(f"{result.id} [{result.source_type}; {approval}] {result.title}")
        typer.echo(f"  {result.path}")
        if result.snippet:
            typer.echo(f"  {result.snippet}")


@db_app.command("status")
def db_status() -> None:
    """Show database path, migration version, and candidate index size."""

    try:
        status = _database().status()
    except Exception as error:
        typer.echo(f"DB STATUS FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    for key, value in status.items():
        typer.echo(f"{key}: {value}")


@config_app.command("check")
def config_check() -> None:
    """Show whether required local integrations are configured."""

    try:
        settings = Settings.load(_root(), require_browserbase=False)
    except ConfigurationError as error:
        typer.echo(f"CONFIG INVALID: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"browserbase_api_key: {settings.masked_browserbase_api_key}")
    typer.echo(f"browserbase_project_id: {settings.browserbase_project_id or 'not configured'}")
    typer.echo(f"browserbase_api_base_url: {settings.browserbase_api_base_url}")
    typer.echo(f"browser_use_api_key: {settings.masked_browser_use_api_key}")
    typer.echo(f"browser_use_model: {settings.browser_use_model}")
    workspace = effective_config(_root())
    typer.echo(f"workspace_root: {workspace.workspace_path}")
    typer.echo(f"documents_root: {workspace.documents_path}")
    typer.echo(f"agent_provider: {workspace.agent_provider}")
    typer.echo(f"user_config: {config_path() if config_path().exists() else 'not initialized'}")


@config_app.command("workspace")
def config_workspace(
    workspace: Annotated[Path, typer.Argument(help="Workspace directory to select.")],
) -> None:
    """Select an existing or new local workspace."""

    try:
        path = workspace.expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        update_config(workspace_root=path)
    except Exception as error:
        typer.echo(f"WORKSPACE CONFIG FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Selected workspace: {path}")


@config_app.command("provider")
def config_provider(
    provider: Annotated[str, typer.Argument(help="auto, codex, or claude.")],
) -> None:
    """Choose the local CLI used by agent tasks."""

    normalized = provider.casefold()
    if normalized not in {"auto", "codex", "claude"}:
        typer.echo("PROVIDER ERROR: expected auto, codex, or claude", err=True)
        raise typer.Exit(code=1)
    try:
        update_config(agent_provider=normalized)  # type: ignore[arg-type]
    except Exception as error:
        typer.echo(f"PROVIDER CONFIG FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Local agent provider: {normalized}")


@documents_app.command("list")
def documents_list() -> None:
    """Refresh and list supported files in the selected document folder."""

    try:
        records = inventory(_root())
    except Exception as error:
        typer.echo(f"DOCUMENT INVENTORY FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Document folder: {effective_config(_root()).documents_path}")
    if not records:
        typer.echo("No supported documents found.")
        return
    for record in records:
        typer.echo(f"{record.path} [{record.extension}; {record.size_bytes} bytes]")
        typer.echo(f"  sha256: {record.content_hash}")


@documents_app.command("import")
def documents_import(
    source: Annotated[Path, typer.Argument(help="Local document to copy into the inbox.")],
) -> None:
    """Copy one supported document into the selected local inbox."""

    try:
        record = import_document(source, _root())
    except Exception as error:
        typer.echo(f"DOCUMENT IMPORT FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Imported: {record.path}")
    typer.echo(f"SHA-256: {record.content_hash}")


@documents_app.command("folder")
def documents_folder(
    folder: Annotated[Path, typer.Argument(help="Existing or new local document folder.")],
) -> None:
    """Select a document folder, including one outside the workspace."""

    try:
        path = folder.expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        update_config(documents_root=path)
    except Exception as error:
        typer.echo(f"DOCUMENT FOLDER FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Selected document folder: {path}")


@agent_app.command("check")
def agent_check() -> None:
    """Report which local provider CLIs are available on PATH."""

    try:
        configured = effective_config(_root()).agent_provider
        providers = available_providers()
    except Exception as error:
        typer.echo(f"AGENT CHECK FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"configured_provider: {configured}")
    for provider, available in providers.items():
        typer.echo(f"{provider}: {'available' if available else 'not found'}")


@agent_app.command("run")
def agent_run(
    prompt: Annotated[str, typer.Argument(help="Task prompt for the local CLI.")],
    provider: Annotated[
        str | None, typer.Option("--provider", help="codex or claude; defaults to local config.")
    ] = None,
    timeout: Annotated[int, typer.Option("--timeout", min=1, max=3600)] = 300,
) -> None:
    """Run one local provider task without exposing credentials to Jobber."""

    selected = provider or effective_config(_root()).agent_provider
    if selected == "auto":
        selected = next(
            (name for name, available in available_providers().items() if available),
            "",
        )
    if selected not in {"codex", "claude"}:
        typer.echo("AGENT RUN FAILED: choose codex or claude, or install one of them.", err=True)
        raise typer.Exit(code=1)
    try:
        result = LocalCliRunner().run(
            AgentTask(provider=selected, prompt=prompt, cwd=_root(), timeout_seconds=timeout)  # type: ignore[arg-type]
        )
    except LocalAgentError as error:
        typer.echo(f"AGENT RUN FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    if result.text:
        typer.echo(result.text)
    if not result.success:
        typer.echo(result.error or "local agent failed", err=True)
        raise typer.Exit(code=1)


@job_app.command("discover")
def job_discover(
    source: Annotated[str, typer.Argument(help="greenhouse, lever, or ashby")],
    board: Annotated[str, typer.Argument(help="Public board token/name.")],
) -> None:
    """Fetch a public board and store normalized jobs."""

    source_name = source.casefold()
    source_adapter: JobSource
    if source_name == "greenhouse":
        source_adapter = GreenhouseSource(board)
    elif source_name == "lever":
        source_adapter = LeverSource(board)
    elif source_name == "ashby":
        source_adapter = AshbySource(board)
    else:
        typer.echo("SOURCE ERROR: expected greenhouse, lever, or ashby", err=True)
        raise typer.Exit(code=1)
    try:
        raw_jobs = asyncio.run(source_adapter.fetch_jobs())
        ids = JobAgentService().ingest(raw_jobs)
    except Exception as error:
        typer.echo(f"DISCOVERY FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Stored {len(ids)} jobs from {source_name}.")


@job_app.command("discover-simplifyjobs")
def job_discover_simplifyjobs(
    role: Annotated[str, typer.Option("--role", help="internship or newgrad.")] = "internship",
    timeframe: Annotated[
        str, typer.Option("--timeframe", help="lastday, lastweek, or lastmonth.")
    ] = "lastday",
    location: Annotated[
        str, typer.Option("--location", help="Location substring, or all.")
    ] = "all",
) -> None:
    """Fetch current internship or new-grad postings from SimplifyJobs feeds."""

    _run_simplifyjobs_discovery(role=role, timeframe=timeframe, location=location)


@job_app.command("discover-swelist")
def job_discover_swelist(
    role: Annotated[str, typer.Option("--role", help="internship or newgrad.")] = "internship",
    timeframe: Annotated[
        str, typer.Option("--timeframe", help="lastday, lastweek, or lastmonth.")
    ] = "lastday",
    location: Annotated[
        str, typer.Option("--location", help="Location substring, or all.")
    ] = "all",
) -> None:
    """Compatibility alias for ``discover-simplifyjobs``."""

    _run_simplifyjobs_discovery(role=role, timeframe=timeframe, location=location)


def _run_simplifyjobs_discovery(*, role: str, timeframe: str, location: str) -> None:
    """Run the canonical SimplifyJobs discovery command."""

    try:
        ids = JobAgentService().discover_simplifyjobs(
            role=role,
            timeframe=timeframe,
            location=location,
        )
    except Exception as error:
        typer.echo(f"SIMPLIFYJOBS DISCOVERY FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        f"Stored {len(ids)} jobs from SimplifyJobs "
        f"(role={role}, timeframe={timeframe}, location={location})."
    )


@job_app.command("list")
def job_list(
    status: Annotated[str | None, typer.Option("--status")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=500)] = 50,
) -> None:
    """List normalized jobs."""

    try:
        jobs = JobAgentService().list_jobs(status=status, limit=limit)
    except Exception as error:
        typer.echo(f"JOB LIST FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    if not jobs:
        typer.echo("No jobs found.")
        return
    for job in jobs:
        typer.echo(f"{job['id']} [{job['status']}] {job['company']} — {job['title']}")
        typer.echo(f"  {job['location'] or 'location unknown'} | {job['url']}")


@job_app.command("extract-opportunities")
def job_extract_opportunities(
    limit: Annotated[int, typer.Option("--limit", min=1, max=500)] = 500,
) -> None:
    """Materialize source-grounded, structured opportunity documents."""

    try:
        count = JobAgentService().extract_opportunities(limit=limit)
    except Exception as error:
        typer.echo(f"OPPORTUNITY EXTRACTION FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Extracted {count} opportunity documents.")


@job_app.command("extract-opportunity")
def job_extract_opportunity(
    job_id: Annotated[str, typer.Argument(help="Normalized job ID.")],
) -> None:
    """Extract and persist one source-grounded opportunity document."""

    try:
        opportunity = JobAgentService().materialize_opportunity(job_id)
    except Exception as error:
        typer.echo(f"OPPORTUNITY EXTRACTION FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(json.dumps(opportunity.model_dump(mode="json"), indent=2))


@job_app.command("evaluate")
def job_evaluate(job_id: Annotated[str, typer.Argument(help="Normalized job ID.")]) -> None:
    """Evaluate eligibility, fit, importance, and tier."""

    try:
        evaluation = JobAgentService().evaluate(job_id)
    except Exception as error:
        typer.echo(f"EVALUATION FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(json.dumps(evaluation.model_dump(mode="json"), indent=2))


@application_app.command("prepare")
def application_prepare(job_id: Annotated[str, typer.Argument(help="Normalized job ID.")]) -> None:
    """Create a reviewable application packet."""

    try:
        packet = JobAgentService().prepare(job_id)
    except Exception as error:
        typer.echo(f"PREPARATION FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(packet.markdown)


@application_app.command("status")
def application_status(
    application_id: Annotated[str, typer.Argument(help="Application ID.")],
) -> None:
    """Show one application state."""

    try:
        application = JobAgentService().application_status(application_id)
    except Exception as error:
        typer.echo(f"APPLICATION STATUS FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(json.dumps(application.__dict__, indent=2))


@application_app.command("run")
def application_run(
    application_id: Annotated[str, typer.Argument(help="Application ID.")],
    apply_url: Annotated[
        str | None, typer.Option("--apply-url", help="Override the stored application URL.")
    ] = None,
    max_steps: Annotated[int, typer.Option("--max-steps", min=1, max=500)] = 40,
) -> None:
    """Run Browser Use interactively and stop before final submission."""

    def ask_human(question: HumanQuestion) -> str:
        typer.echo("\nHuman input required")
        typer.echo(f"Question: {question.question}")
        if question.context:
            typer.echo(f"Context: {question.context}")
        if question.allowed_options:
            typer.echo("Allowed options: " + ", ".join(question.allowed_options))
        return typer.prompt("Answer")

    try:
        result = JobAgentService().run_browser(
            application_id,
            apply_url=apply_url,
            max_steps=max_steps,
            human_escalation=ask_human,
        )
    except Exception as error:
        typer.echo(f"BROWSER RUN FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(json.dumps(result.__dict__, indent=2))


@application_app.command("browser-links")
def application_browser_links(
    application_id: Annotated[str, typer.Argument(help="Application ID.")],
) -> None:
    """Show a live view or the Browserbase Session Inspector replay link."""

    try:
        links = JobAgentService().browser_session_links(application_id)
    except Exception as error:
        typer.echo(f"BROWSER LINKS FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(json.dumps(links, indent=2))


@application_app.command("approve")
def application_approve(
    application_id: Annotated[str, typer.Argument(help="Application ID.")],
) -> None:
    """Record human approval while keeping final submission disabled."""

    try:
        application = JobAgentService().approve_submission(application_id)
    except Exception as error:
        typer.echo(f"APPROVAL FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"{application.id}: status={application.status}; final submission remains disabled.")


@application_app.command("answer")
def application_answer(
    application_id: Annotated[str, typer.Argument(help="Application ID.")],
    question: Annotated[str, typer.Argument(help="Question text.")],
    answer: Annotated[str, typer.Argument(help="Human-provided answer.")],
) -> None:
    """Record a human-provided answer with an event trail."""

    try:
        answer_id = JobAgentService().record_user_answer(
            application_id=application_id,
            question=question,
            answer=answer,
        )
    except Exception as error:
        typer.echo(f"ANSWER FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Recorded user answer: {answer_id}")


@learning_app.command("report")
def learning_report() -> None:
    """Show aggregate human-edit and feedback signals."""

    try:
        report = JobAgentService().learning_report()
    except Exception as error:
        typer.echo(f"LEARNING REPORT FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(json.dumps(report.as_dict(), indent=2))


@learning_app.command("feedback")
def learning_feedback(
    artifact_type: Annotated[
        str, typer.Argument(help="Answer, packet, resume, or other artifact.")
    ],
    artifact_id: Annotated[str, typer.Argument(help="Stable artifact ID.")],
    original_text: Annotated[str, typer.Argument(help="Original generated text.")],
    edited_text: Annotated[str, typer.Argument(help="Human-edited or final text.")],
    feedback_type: Annotated[
        str, typer.Argument(help="Feedback label, such as minor_edit or rejected.")
    ],
    application_id: Annotated[str | None, typer.Option("--application-id")] = None,
) -> None:
    """Record an explicit human edit or rejection for later reporting."""

    try:
        feedback_id = JobAgentService().record_feedback(
            application_id=application_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            original_text=original_text,
            edited_text=edited_text,
            feedback_type=feedback_type,
        )
    except Exception as error:
        typer.echo(f"FEEDBACK FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Recorded feedback: {feedback_id}")


@resume_app.command("add")
def resume_add(
    resume_id: Annotated[str, typer.Argument(help="Stable resume ID.")],
    name: Annotated[str, typer.Argument(help="Human-readable resume name.")],
    source_path: Annotated[str, typer.Argument(help="Path to the approved source resume.")],
    base_type: Annotated[str, typer.Option("--base-type")] = "general",
    version: Annotated[str, typer.Option("--version")] = "1",
    rendered_path: Annotated[str | None, typer.Option("--rendered-path")] = None,
) -> None:
    """Register a resume for packet preparation and browser upload."""

    try:
        _require_file(source_path, "Resume source")
        if rendered_path:
            _require_file(rendered_path, "Rendered resume")
        ApplicationRepository(_database()).upsert_resume(
            ResumeRecord(
                id=resume_id,
                name=name,
                base_type=base_type,
                source_path=source_path,
                rendered_path=rendered_path,
                version=version,
            )
        )
    except Exception as error:
        typer.echo(f"RESUME ADD FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Registered resume: {resume_id}")


def _require_file(value: str, label: str) -> None:
    path = Path(value)
    resolved = path if path.is_absolute() else _root() / path
    if not resolved.is_file():
        raise ValueError(f"{label} file does not exist: {value}")


@resume_app.command("list")
def resume_list() -> None:
    """List registered resumes."""

    try:
        resumes = ApplicationRepository(_database()).resumes()
    except Exception as error:
        typer.echo(f"RESUME LIST FAILED: {error}", err=True)
        raise typer.Exit(code=1) from error
    if not resumes:
        typer.echo("No resumes registered.")
        return
    for resume in resumes:
        typer.echo(f"{resume.id}: {resume.name} [{resume.base_type}] {resume.source_path}")


if __name__ == "__main__":
    app()

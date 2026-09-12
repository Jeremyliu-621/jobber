"""Typer command-line interface for the first application-system slice."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer

from .candidate import CandidateFactStore, CandidateIndexer, load_profile
from .config import ConfigurationError, Settings
from .db import ApplicationRepository, CandidateSourceRepository, Database, ResumeRecord
from .discovery import AshbySource, GreenhouseSource, LeverSource
from .discovery.sources import JobSource
from .service import JobAgentService

app = typer.Typer(help="Personal SWE job application system.")
candidate_app = typer.Typer(help="Inspect and search the candidate brain.")
db_app = typer.Typer(help="Inspect application state storage.")
config_app = typer.Typer(help="Inspect local runtime configuration.")
job_app = typer.Typer(help="Discover, evaluate, and list jobs.")
application_app = typer.Typer(help="Prepare and inspect applications.")
learning_app = typer.Typer(help="Inspect feedback and learning signals.")
resume_app = typer.Typer(help="Manage the local resume inventory.")
app.add_typer(candidate_app, name="candidate")
app.add_typer(db_app, name="db")
app.add_typer(config_app, name="config")
app.add_typer(job_app, name="job")
app.add_typer(application_app, name="application")
app.add_typer(learning_app, name="learning")
app.add_typer(resume_app, name="resume")


def _root() -> Path:
    return Path.cwd()


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

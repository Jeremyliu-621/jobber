"""Build reviewable application packets without inventing candidate facts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from job_agent.db import ApplicationRepository, CandidateSourceRepository, Database, JobRepository
from job_agent.models import ApplicationPlan, QualityReport, ResumeChoice
from job_agent.scoring import JobEvaluator


@dataclass(frozen=True)
class PreparedPacket:
    plan: ApplicationPlan
    markdown: str


class ApplicationPlanner:
    def __init__(self, *, project_root: Path, database: Database) -> None:
        self.project_root = Path(project_root)
        self.database = database
        self.jobs = JobRepository(database)
        self.applications = ApplicationRepository(database)
        self.sources = CandidateSourceRepository(database)
        self.evaluator = JobEvaluator(project_root=self.project_root, database=database)

    def prepare(self, job_id: str) -> PreparedPacket:
        job = self.jobs.get(job_id)
        if job is None:
            raise ValueError(f"Unknown job: {job_id}")
        evaluation = self.evaluator.evaluate(job)
        self.jobs.save_criteria(job.id, evaluation.fit.criteria)
        self.jobs.save_evidence(evaluation.fit.evidence)
        self.jobs.save_evaluation(evaluation)
        self.jobs.update_status(job.id, "evaluated")

        existing = self.applications.find_for_job(job_id)
        application_id = (
            existing.id
            if existing
            else self.applications.create(
                job_id=job_id,
                tier=evaluation.importance.tier,
                status=_application_status(
                    evaluation.importance.tier, evaluation.eligibility.status
                ),
            )
        )
        resume_choice = self._select_resume(evaluation.fit.criteria)
        status = _application_status(evaluation.importance.tier, evaluation.eligibility.status)
        if existing and existing.status in {"preparing", "ready_to_submit", "submitted"}:
            status = existing.status
        self.applications.update_plan(
            application_id,
            tier=evaluation.importance.tier,
            status=status,
            resume_id=resume_choice.resume_id if resume_choice else None,
        )
        self.applications.add_event(
            application_id,
            "plan_created",
            {
                "tier": evaluation.importance.tier,
                "eligibility": evaluation.eligibility.status,
                "fit_score": evaluation.fit.score,
                "importance_score": evaluation.importance.score,
                "resume_id": resume_choice.resume_id if resume_choice else None,
            },
        )
        quality = self._packet_quality(evaluation, resume_choice)
        next_action = _next_action(
            evaluation.importance.tier, evaluation.eligibility.status, quality
        )
        plan = ApplicationPlan(
            application_id=application_id,
            job_id=job.id,
            eligibility=evaluation.eligibility,
            fit=evaluation.fit,
            importance=evaluation.importance,
            resume=resume_choice,
            quality=quality,
            next_action=next_action,
        )
        return PreparedPacket(plan=plan, markdown=self._render_markdown(job, plan))

    def _select_resume(self, criteria) -> ResumeChoice | None:
        resumes = self.applications.resumes()
        if not resumes:
            return None
        criterion_names = {criterion.name.casefold() for criterion in criteria}
        ranked = sorted(
            resumes,
            key=lambda resume: len(criterion_names & set(resume.base_type.casefold().split("+"))),
            reverse=True,
        )
        selected = ranked[0]
        return ResumeChoice(
            resume_id=selected.id,
            reasons=["Selected from the local resume inventory; review before upload."],
            selected_source_ids=[],
        )

    def _packet_quality(self, evaluation, resume: ResumeChoice | None) -> QualityReport:
        notes = [
            (
                "No free-response text was generated; answer drafting requires "
                "retrieved candidate evidence."
            ),
            "Final submission is disabled by policy.",
        ]
        if evaluation.eligibility.missing_facts:
            notes.append("Missing facts: " + ", ".join(evaluation.eligibility.missing_facts))
        resume_ready = False
        if resume is None:
            notes.append("No resume is registered in the local inventory.")
        else:
            record = next(
                (item for item in self.applications.resumes() if item.id == resume.resume_id),
                None,
            )
            if record is None:
                notes.append("Selected resume is missing from the local inventory.")
            else:
                source_path = self._local_path(record.source_path)
                if not source_path.is_file():
                    notes.append(f"Resume source file is missing: {record.source_path}")
                rendered_path = (
                    self._local_path(record.rendered_path)
                    if record.rendered_path
                    else source_path if source_path.suffix.casefold() == ".pdf" else None
                )
                if rendered_path is None or not rendered_path.is_file():
                    notes.append(
                        "A rendered PDF resume is required before browser preparation."
                    )
                else:
                    resume_ready = True
        passed = evaluation.eligibility.status == "pass" and resume_ready
        return QualityReport(
            passed=passed,
            grounding_score=1.0,
            style_score=1.0,
            notes=notes,
        )

    def _local_path(self, value: str | None) -> Path:
        if not value:
            return self.project_root / "candidate" / "resumes"
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    @staticmethod
    def _render_markdown(job, plan: ApplicationPlan) -> str:
        criteria_lines = [
            f"- **{criterion.name}** ({criterion.category}, weight {criterion.weight:g})"
            f" — {criterion.source_text}"
            for criterion in plan.fit.criteria
        ] or ["- No standard skill criteria were extracted."]
        gap_lines = [f"- {gap}" for gap in plan.fit.gaps] or ["- None detected"]
        missing_lines = [f"- {fact}" for fact in plan.eligibility.missing_facts] or ["- None"]
        resume = plan.resume.resume_id if plan.resume else "None registered"
        notes = "\n".join(f"- {note}" for note in (plan.quality.notes if plan.quality else []))
        return "\n".join(
            [
                f"# Application packet — {job.company} / {job.title}",
                "",
                f"- Job ID: `{job.id}`",
                f"- Application ID: `{plan.application_id}`",
                f"- URL: {job.apply_url or job.url}",
                f"- Eligibility: **{plan.eligibility.status}**",
                f"- Fit: **{plan.fit.score:.1f}/100**",
                f"- Importance: **{plan.importance.score:.1f}/100** ({plan.importance.tier})",
                f"- Recommended next action: **{plan.next_action}**",
                f"- Resume: `{resume}`",
                "",
                "## Eligibility reasons",
                *[f"- {reason}" for reason in plan.eligibility.reasons],
                "",
                "## Missing facts",
                *missing_lines,
                "",
                "## Extracted criteria",
                *criteria_lines,
                "",
                "## Evidence gaps",
                *gap_lines,
                "",
                "## Quality gate",
                f"- Passed: **{plan.quality.passed if plan.quality else False}**",
                notes,
                "",
                "No answer or submission is generated automatically by this packet.",
            ]
        )


def _application_status(tier: str, eligibility: str) -> str:
    if tier == "skip":
        return "skipped"
    if eligibility == "uncertain":
        return "needs_user"
    if tier == "tier_a":
        return "tier_a_manual"
    return "ready_for_review"


def _next_action(tier: str, eligibility: str, quality: QualityReport) -> str:
    if tier == "skip":
        return "skip"
    if eligibility != "pass":
        return "answer_missing_facts"
    if not quality.passed:
        return "register_resume_and_review"
    if tier == "tier_a":
        return "manual_application"
    return "review_before_browser"

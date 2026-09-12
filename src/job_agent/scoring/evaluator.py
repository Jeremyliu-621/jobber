"""Inspectable eligibility, fit, and importance evaluation."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from job_agent.candidate import CandidateFactStore, load_profile
from job_agent.db import CandidateSource, CandidateSourceRepository, JobRepository
from job_agent.models import (
    EligibilityResult,
    Evidence,
    FitEvaluation,
    ImportanceEvaluation,
    Job,
    JobCriterion,
    JobEvaluation,
)


@dataclass(frozen=True)
class SkillPattern:
    label: str
    expressions: tuple[str, ...]


SKILLS = (
    SkillPattern("python", (r"\bpython\b",)),
    SkillPattern("javascript", (r"\bjavascript\b", r"\bjs\b")),
    SkillPattern("typescript", (r"\btypescript\b", r"\bts\b")),
    SkillPattern("java", (r"\bjava\b",)),
    SkillPattern("c++", (r"c\+\+",)),
    SkillPattern("go", (r"\bgolang\b", r"\bgo\s+programming\b")),
    SkillPattern("rust", (r"\brust\b",)),
    SkillPattern("sql", (r"\bsql\b",)),
    SkillPattern("postgresql", (r"\bpostgres(?:ql)?\b",)),
    SkillPattern("mysql", (r"\bmysql\b",)),
    SkillPattern("redis", (r"\bredis\b",)),
    SkillPattern("aws", (r"\baws\b", r"amazon web services")),
    SkillPattern("gcp", (r"\bgcp\b", r"google cloud")),
    SkillPattern("azure", (r"\bazure\b",)),
    SkillPattern("docker", (r"\bdocker\b",)),
    SkillPattern("kubernetes", (r"\bkubernetes\b", r"\bk8s\b")),
    SkillPattern("git", (r"\bgit\b",)),
    SkillPattern("react", (r"\breact(?:\.js)?\b",)),
    SkillPattern("node.js", (r"\bnode(?:\.js)?\b",)),
    SkillPattern("graphql", (r"\bgraphql\b",)),
    SkillPattern("machine learning", (r"\bmachine learning\b", r"\bml\b")),
    SkillPattern("llms", (r"\bllms?\b", r"large language models?")),
    SkillPattern("testing", (r"\btesting\b", r"\bunit tests?\b")),
)


class JobEvaluator:
    """Evaluate jobs using candidate facts and indexed candidate evidence."""

    VERSION = "deterministic-v1"

    def __init__(self, *, project_root: Path, database) -> None:
        self.project_root = Path(project_root)
        self.database = database
        self.sources = CandidateSourceRepository(database)
        self.jobs = JobRepository(database)
        self.profile = load_profile(self.project_root / "candidate" / "profile.yaml")
        self.facts = CandidateFactStore(self.profile)

    def evaluate(self, job: Job) -> JobEvaluation:
        criteria = extract_criteria(job)
        evidence = self._evidence_for(criteria)
        eligibility = self._eligibility(job)
        fit = self._fit(job, criteria, evidence)
        importance = self._importance(job, fit.score, eligibility)
        summary = self._summary(job, eligibility, fit, importance)
        evaluation_id = "evaluation.{}".format(
            hashlib.sha256(f"{job.id}:{self.VERSION}".encode()).hexdigest()[:20]
        )
        return JobEvaluation(
            id=evaluation_id,
            job_id=job.id,
            eligibility=eligibility,
            fit=fit,
            importance=importance,
            summary=summary,
            version=self.VERSION,
        )

    def persist(self, job: Job) -> JobEvaluation:
        evaluation = self.evaluate(job)
        self.jobs.upsert(job)
        self.jobs.save_criteria(job.id, evaluation.fit.criteria)
        self.jobs.save_evidence(evaluation.fit.evidence)
        self.jobs.save_evaluation(evaluation)
        self.jobs.update_status(job.id, "evaluated")
        return evaluation

    def _evidence_for(self, criteria: Iterable[JobCriterion]) -> dict[str, list[Evidence]]:
        evidence: dict[str, list[Evidence]] = {}
        for criterion in criteria:
            matches = self.sources.search(criterion.name, top_k=5)
            evidence[criterion.id] = [
                Evidence(
                    source_id=source.id,
                    strength=_source_strength(source, criterion.name),
                    notes=f"Retrieved from {source.path}",
                )
                for source in matches
                if source.approved or source.source_type == "fact"
            ]
        return evidence

    def _eligibility(self, job: Job) -> EligibilityResult:
        text = f"{job.title} {job.location or ''} {job.description_text}".casefold()
        reasons: list[str] = []
        missing: list[str] = []
        status: Literal["pass", "fail", "uncertain"] = "pass"

        if any(
            marker in text
            for marker in ("new grad", "new graduate", "intern", "internship", "student")
        ):
            if not self.facts.get("education.0.graduation_date"):
                missing.append("education.0.graduation_date")
                status = "uncertain"
                reasons.append(
                    "The role has a student or new-graduate signal, but graduation date is unknown."
                )

        country = _country_for_job(job)
        if country:
            authorized_path = f"work_authorization.{country}.authorized"
            authorized = self.facts.get(authorized_path)
            if authorized is None:
                missing.append(authorized_path)
                status = "uncertain"
                reasons.append(f"Work authorization for {country.upper()} is unknown.")
            elif authorized.value is False:
                status = "fail"
                reasons.append(f"Candidate is not authorized to work in {country.upper()}.")

        if _requires_sponsorship(text):
            sponsorship_path = f"work_authorization.{country or 'usa'}.sponsorship_required"
            sponsorship = self.facts.get(sponsorship_path)
            if sponsorship is None:
                missing.append(sponsorship_path)
                status = "uncertain" if status != "fail" else status
                reasons.append("The job mentions sponsorship and the candidate policy is unknown.")
            elif sponsorship.value is True:
                status = "uncertain" if status != "fail" else status
                reasons.append(
                    "The candidate requires sponsorship; role sponsorship "
                    "compatibility needs review."
                )

        location_result = self._location_check(job)
        if location_result == "uncertain":
            status = "uncertain" if status != "fail" else status
            missing.append("preferences.locations")
            reasons.append("Role location does not clearly match the stored location preferences.")
        elif location_result == "fail":
            status = "fail"
            reasons.append("Role location conflicts with the stored location preferences.")

        if not reasons:
            reasons.append("No hard eligibility conflict was found from known facts.")
        return EligibilityResult(status=status, reasons=reasons, missing_facts=sorted(set(missing)))

    def _location_check(self, job: Job) -> str:
        locations = [
            location.casefold()
            for location in self.profile.preferences.locations
            if location.strip()
        ]
        if not locations or not job.location:
            return "pass"
        role_location = job.location.casefold()
        if "remote" in role_location and self.profile.preferences.remote is not False:
            return "pass"
        if any(location in role_location or role_location in location for location in locations):
            return "pass"
        if (
            self.profile.preferences.remote is True
            and "remote" in f"{job.title} {job.description_text}".casefold()
        ):
            return "pass"
        return "uncertain"

    def _fit(
        self,
        job: Job,
        criteria: list[JobCriterion],
        evidence: dict[str, list[Evidence]],
    ) -> FitEvaluation:
        if criteria:
            weighted_total = sum(criterion.weight for criterion in criteria)
            weighted_supported = sum(
                criterion.weight
                * max((item.strength for item in evidence.get(criterion.id, [])), default=0)
                for criterion in criteria
            )
            criteria_score = 100 * weighted_supported / weighted_total if weighted_total else 0
        else:
            criteria_score = 50

        role_score = _role_match(job.title, self.profile.preferences.target_roles)
        score = round(criteria_score * 0.75 + role_score * 0.25, 2)
        gaps = [criterion.name for criterion in criteria if not evidence.get(criterion.id)]
        return FitEvaluation(score=score, criteria=criteria, evidence=evidence, gaps=gaps)

    def _importance(
        self,
        job: Job,
        fit_score: float,
        eligibility: EligibilityResult,
    ) -> ImportanceEvaluation:
        title = job.title.casefold()
        company = job.company.casefold()
        preferences = self.profile.preferences
        role_preference = _role_match(job.title, preferences.target_roles)
        company_signal = (
            100 if any(item.casefold() in company for item in preferences.target_companies) else 0
        )
        referral_signal = (
            100 if any(item.casefold() in company for item in preferences.referral_companies) else 0
        )
        keyword_signal = (
            100
            if any(
                item.casefold() in f"{title} {job.description_text}".casefold()
                for item in preferences.excitement_keywords
            )
            else 0
        )
        preference_score = max(role_preference, company_signal, referral_signal, keyword_signal)
        score = round(fit_score * 0.7 + preference_score * 0.2 + 50 * 0.1, 2)
        if eligibility.status == "fail":
            score = min(score, 59.0)
        elif eligibility.status == "uncertain":
            score = min(score, 74.0)
        tier = _tier_for_score(score)
        reasons = [f"Fit score contributes {fit_score:.1f}/100."]
        if role_preference:
            reasons.append("The role matches a stored target-role preference.")
        if company_signal:
            reasons.append("The company is in stored target companies.")
        if referral_signal:
            reasons.append("A referral or recruiter connection is recorded for this company.")
        if eligibility.status != "pass":
            reasons.append("Eligibility uncertainty lowers the maximum importance tier.")
        return ImportanceEvaluation(score=score, reasons=reasons, tier=tier)

    @staticmethod
    def _summary(
        job: Job,
        eligibility: EligibilityResult,
        fit: FitEvaluation,
        importance: ImportanceEvaluation,
    ) -> str:
        gap_text = ", ".join(fit.gaps[:4]) or "no extracted evidence gaps"
        return (
            f"{job.company} / {job.title}: eligibility {eligibility.status}; "
            f"fit {fit.score:.1f}; importance {importance.score:.1f}; "
            f"tier {importance.tier}; gaps: {gap_text}."
        )


def extract_criteria(job: Job) -> list[JobCriterion]:
    """Extract a small, explainable criterion set from the job description."""

    text = f"{job.title}. {job.description_text}"
    lower = text.casefold()
    criteria: list[JobCriterion] = []
    for skill in SKILLS:
        if not any(re.search(expression, lower) for expression in skill.expressions):
            continue
        sentence = _sentence_for_skill(text, skill.expressions)
        category = _category_for_sentence(sentence)
        weight = {"required": 1.0, "preferred": 0.6, "contextual": 0.25}[category]
        criterion_id = "criterion.{}".format(
            hashlib.sha256(f"{job.id}:{skill.label}".encode()).hexdigest()[:18]
        )
        criteria.append(
            JobCriterion(
                id=criterion_id,
                job_id=job.id,
                name=skill.label,
                category=category,
                weight=weight,
                source_text=sentence,
            )
        )
    return criteria


def _sentence_for_skill(text: str, expressions: Iterable[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    for sentence in sentences:
        if any(re.search(expression, sentence.casefold()) for expression in expressions):
            return " ".join(sentence.split())[:500]
    return " ".join(text.split())[:500]


def _category_for_sentence(
    sentence: str,
) -> Literal["required", "preferred", "contextual"]:
    lower = sentence.casefold()
    if any(
        marker in lower
        for marker in ("required", "must have", "must be", "minimum", "qualifications")
    ):
        return "required"
    if any(marker in lower for marker in ("preferred", "nice to have", "bonus", "plus", "ideally")):
        return "preferred"
    return "contextual"


def _source_strength(source: CandidateSource, criterion: str) -> float:
    content = f"{source.title} {source.content}".casefold()
    if criterion.casefold() not in content:
        return 0.35 if source.approved else 0.0
    return 1.0 if source.approved else 0.55


def _country_for_job(job: Job) -> str | None:
    text = f"{job.location or ''} {job.description_text}".casefold()
    if any(
        marker in text
        for marker in (
            "united states",
            "u.s.",
            "usa",
            "new york",
            "california",
            "seattle",
            "boston",
            "san francisco",
            "los angeles",
            "palo alto",
            "torrance",
            "chicago",
            "atlanta",
            "georgia",
            "texas",
            "massachusetts",
            "washington",
        )
    ) or _has_us_state_code(job.location):
        return "usa"
    if any(
        marker in text
        for marker in ("canada", "toronto", "vancouver", "montreal", "ottawa", "waterloo")
    ):
        return "canada"
    return None


def _has_us_state_code(location: str | None) -> bool:
    """Recognize the state abbreviation format used by public ATS locations."""

    if not location:
        return False
    state_codes = (
        "al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy"
    )
    return bool(re.search(rf",\s*(?:{state_codes})\b", location.casefold()))


def _requires_sponsorship(text: str) -> bool:
    return any(
        marker in text for marker in ("sponsorship", "visa sponsorship", "immigration support")
    )


def _role_match(title: str, target_roles: Iterable[str]) -> float:
    roles = [role.casefold().strip() for role in target_roles if role.strip()]
    if not roles:
        return 50.0
    title_lower = title.casefold()
    return 100.0 if any(role in title_lower or title_lower in role for role in roles) else 25.0


def _tier_for_score(score: float) -> Literal["skip", "tier_a", "tier_b", "tier_c"]:
    if score >= 90:
        return "tier_a"
    if score >= 75:
        return "tier_b"
    if score >= 60:
        return "tier_c"
    return "skip"

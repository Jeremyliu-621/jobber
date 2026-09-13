"""Domain models shared by the planner, database, and future interfaces."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Job(DomainModel):
    id: str
    source: str
    source_job_id: str | None = None
    company: str
    title: str
    location: str | None = None
    url: HttpUrl
    apply_url: HttpUrl | None = None
    description_text: str = ""
    posted_at: datetime | None = None
    status: str = "discovered"
    dedupe_hash: str
    raw_payload: dict = Field(default_factory=dict)


class OpportunitySection(DomainModel):
    """One source-grounded, display-ready section of a job opportunity."""

    key: str
    label: str
    kind: Literal["paragraph", "list"]
    items: list[str] = Field(min_length=1)
    source_text: str


class OpportunityDocument(DomainModel):
    """The structured opportunity derived from one normalized job record."""

    job_id: str
    source_hash: str
    extractor_version: str
    sections: list[OpportunitySection] = Field(min_length=1)


class JobCriterion(DomainModel):
    id: str
    job_id: str
    name: str
    category: Literal["required", "preferred", "contextual"]
    weight: float = Field(ge=0)
    source_text: str = ""


class Evidence(DomainModel):
    source_id: str
    strength: float = Field(ge=0, le=1)
    notes: str = ""


class EligibilityResult(DomainModel):
    status: Literal["pass", "fail", "uncertain"]
    reasons: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)


class FitEvaluation(DomainModel):
    score: float = Field(ge=0, le=100)
    criteria: list[JobCriterion] = Field(default_factory=list)
    evidence: dict[str, list[Evidence]] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)


class ImportanceEvaluation(DomainModel):
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    tier: Literal["skip", "tier_a", "tier_b", "tier_c"]


class JobEvaluation(DomainModel):
    id: str
    job_id: str
    eligibility: EligibilityResult
    fit: FitEvaluation
    importance: ImportanceEvaluation
    summary: str = ""
    version: str = "1"


class ResumeChoice(DomainModel):
    resume_id: str
    reasons: list[str] = Field(default_factory=list)
    selected_source_ids: list[str] = Field(default_factory=list)


class ApplicationQuestion(DomainModel):
    id: str
    application_id: str
    question_text: str
    normalized_question: str
    question_type: str
    required: bool = False
    max_length: int | None = Field(default=None, ge=1)
    source_page: str | None = None


class CandidateClaim(DomainModel):
    claim_text: str
    source_id: str
    support_type: str
    confidence: float = Field(ge=0, le=1)


class QualityReport(DomainModel):
    passed: bool
    grounding_score: float = Field(ge=0, le=1)
    style_score: float = Field(ge=0, le=1)
    unsupported_claims: list[str] = Field(default_factory=list)
    slop_flags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ApplicationPlan(DomainModel):
    application_id: str
    job_id: str
    eligibility: EligibilityResult
    fit: FitEvaluation
    importance: ImportanceEvaluation
    resume: ResumeChoice | None = None
    answer_ids: list[str] = Field(default_factory=list)
    quality: QualityReport | None = None
    next_action: str = "review"

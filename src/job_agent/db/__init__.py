"""SQLite persistence and migrations."""

from .applications import (
    ApplicationAnswerRecord,
    ApplicationRecord,
    ApplicationRepository,
    ResumeRecord,
)
from .connection import Database
from .jobs import JobEvaluationRecord, JobRepository
from .opportunities import OpportunityRepository
from .repository import CandidateSource, CandidateSourceRepository

__all__ = [
    "ApplicationRecord",
    "ApplicationAnswerRecord",
    "ApplicationRepository",
    "CandidateSource",
    "CandidateSourceRepository",
    "Database",
    "JobEvaluationRecord",
    "JobRepository",
    "OpportunityRepository",
    "ResumeRecord",
]

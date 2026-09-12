"""SQLite persistence and migrations."""

from .applications import ApplicationRecord, ApplicationRepository, ResumeRecord
from .connection import Database
from .jobs import JobEvaluationRecord, JobRepository
from .repository import CandidateSource, CandidateSourceRepository

__all__ = [
    "ApplicationRecord",
    "ApplicationRepository",
    "CandidateSource",
    "CandidateSourceRepository",
    "Database",
    "JobEvaluationRecord",
    "JobRepository",
    "ResumeRecord",
]

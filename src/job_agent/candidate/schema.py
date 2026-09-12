"""Pydantic schema for structured candidate facts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Identity(CandidateModel):
    legal_name: str | None = None
    preferred_name: str | None = None
    email: str | None = None
    phone: str | None = None


class Education(CandidateModel):
    institution: str | None = None
    program: str | None = None
    degree: str | None = None
    start_date: str | None = None
    graduation_date: str | None = None
    location: str | None = None
    gpa: float | None = None


class Authorization(CandidateModel):
    authorized: bool | None = None
    sponsorship_required: bool | None = None
    notes: str | None = None


class WorkAuthorization(CandidateModel):
    canada: Authorization = Field(default_factory=Authorization)
    usa: Authorization = Field(default_factory=Authorization)


class Links(CandidateModel):
    github: str | None = None
    linkedin: str | None = None
    portfolio: str | None = None


class Preferences(CandidateModel):
    target_roles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    target_companies: list[str] = Field(default_factory=list)
    referral_companies: list[str] = Field(default_factory=list)
    excitement_keywords: list[str] = Field(default_factory=list)
    remote: bool | None = None


class CandidateProfile(CandidateModel):
    identity: Identity = Field(default_factory=Identity)
    education: list[Education] = Field(default_factory=list)
    work_authorization: WorkAuthorization = Field(default_factory=WorkAuthorization)
    links: Links = Field(default_factory=Links)
    preferences: Preferences = Field(default_factory=Preferences)

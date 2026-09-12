"""Load and validate the structured candidate profile."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from .schema import CandidateProfile


def load_profile(profile_path: Path, *, preferences_path: Path | None = None) -> CandidateProfile:
    """Load profile YAML and optionally merge the sibling preferences file."""

    profile_path = Path(profile_path)
    raw = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Candidate profile must contain a YAML mapping: {profile_path}")

    preference_file = preferences_path or profile_path.with_name("preferences.yaml")
    if preference_file.exists():
        preference_data = yaml.safe_load(preference_file.read_text(encoding="utf-8")) or {}
        if not isinstance(preference_data, dict):
            raise ValueError(
                f"Candidate preferences must contain a YAML mapping: {preference_file}"
            )
        merged = dict(raw)
        merged["preferences"] = {
            **(raw.get("preferences") or {}),
            **preference_data,
        }
        raw = merged
    return CandidateProfile.model_validate(_normalize_yaml_scalars(raw))


def profile_data(profile: CandidateProfile) -> dict[str, Any]:
    """Return a JSON-compatible profile mapping for deterministic traversal."""

    return profile.model_dump(mode="json", exclude_none=False)


def _normalize_yaml_scalars(value: Any) -> Any:
    """Keep YAML's implicit date scalars compatible with string profile fields."""

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize_yaml_scalars(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalize_yaml_scalars(child) for child in value]
    return value

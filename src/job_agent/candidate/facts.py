"""Deterministic candidate fact traversal and lookup."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from .profile import profile_data
from .schema import CandidateProfile


@dataclass(frozen=True)
class CandidateFact:
    path: str
    source_id: str
    value: Any


def _is_known(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_is_known(child) for child in value.values())
    if isinstance(value, list):
        return any(_is_known(child) for child in value)
    return True


def iter_facts(value: Any, path: str = "") -> Iterator[CandidateFact]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from iter_facts(child, child_path)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_facts(child, f"{path}.{index}")
        return
    if _is_known(value):
        yield CandidateFact(path=path, source_id=f"fact.{path}", value=value)


def lookup_path(value: Any, path: str) -> Any:
    """Read a dotted path and return None for missing or unknown values."""

    current = value
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit() and int(segment) < len(current):
            current = current[int(segment)]
        else:
            return None
    return current if _is_known(current) else None


class CandidateFactStore:
    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile
        self._data = profile_data(profile)

    def get(self, path: str) -> CandidateFact | None:
        value = lookup_path(self._data, path)
        if value is None:
            return None
        return CandidateFact(path=path, source_id=f"fact.{path}", value=value)

    def all(self) -> list[CandidateFact]:
        return list(iter_facts(self._data))

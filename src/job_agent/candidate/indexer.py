"""Index structured facts and Markdown candidate knowledge into SQLite."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from job_agent.db import CandidateSourceRepository, Database

from .facts import CandidateFactStore
from .profile import load_profile


@dataclass(frozen=True)
class CandidateDocument:
    source_id: str
    path: str
    source_type: str
    title: str
    approved: bool
    source: str
    topics: tuple[str, ...]
    content: str


class CandidateIndexer:
    def __init__(
        self,
        *,
        candidate_root: Path,
        database: Database,
        project_root: Path | None = None,
    ) -> None:
        self.candidate_root = Path(candidate_root)
        self.project_root = Path(project_root or self.candidate_root.parent)
        self.database = database
        self.repository = CandidateSourceRepository(database)

    def index(self) -> int:
        self.database.migrate()
        count = self._index_profile()
        documents = self._markdown_documents()
        self.repository.remove_missing_markdown_paths(document.path for document in documents)
        for document in documents:
            self.repository.upsert(
                source_id=document.source_id,
                path=document.path,
                source_type=document.source_type,
                title=document.title,
                approved=document.approved,
                source=document.source,
                topics=document.topics,
                content=document.content,
            )
            count += 1
        return count

    def _index_profile(self) -> int:
        profile_path = self.candidate_root / "profile.yaml"
        if not profile_path.exists():
            return 0
        profile = load_profile(profile_path)
        facts = CandidateFactStore(profile).all()
        for fact in facts:
            self.repository.upsert(
                source_id=fact.source_id,
                path=f"{self._relative(profile_path)}#{fact.path}",
                source_type="fact",
                title=fact.path,
                approved=True,
                source="structured-profile",
                topics=("fact", fact.path.split(".", 1)[0]),
                content=str(fact.value),
            )
        return len(facts)

    def _markdown_documents(self) -> list[CandidateDocument]:
        if not self.candidate_root.exists():
            return []
        documents: list[CandidateDocument] = []
        for path in sorted(self.candidate_root.rglob("*.md")):
            relative = path.relative_to(self.project_root).as_posix()
            frontmatter, content = parse_markdown(path.read_text(encoding="utf-8"))
            relative_without_suffix = Path(relative).with_suffix("").as_posix()
            fallback_id = f"doc.{hashlib.sha256(relative.encode('utf-8')).hexdigest()[:16]}"
            source_id = str(frontmatter.get("id") or fallback_id)
            source_type = str(frontmatter.get("type") or path.stem)
            title = str(frontmatter.get("title") or path.stem.replace("-", " ").title())
            topics = _string_tuple(frontmatter.get("topics"))
            source = str(frontmatter.get("source") or "unclassified")
            approved = bool(frontmatter.get("approved", False))
            documents.append(
                CandidateDocument(
                    source_id=source_id,
                    path=relative,
                    source_type=source_type,
                    title=title,
                    approved=approved,
                    source=source,
                    topics=topics or (relative_without_suffix,),
                    content=content,
                )
            )
        return documents

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.project_root).as_posix()


def parse_markdown(text: str) -> tuple[dict[str, Any], str]:
    """Parse optional YAML frontmatter without making Markdown a hard dependency."""

    text = text.lstrip("\ufeff")
    if not text.lstrip().startswith("---"):
        return {}, text.strip()
    match = re.match(r"\A\s*---\s*\n(.*?)\n---\s*(?:\n|$)(.*)\Z", text, flags=re.DOTALL)
    if not match:
        return {}, text.strip()
    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Markdown frontmatter must be a YAML mapping")
    return metadata, match.group(2).strip()


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(item) for item in value if str(item).strip())
    raise ValueError("Frontmatter topics must be a string or list of strings")

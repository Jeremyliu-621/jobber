"""Persistence operations for candidate-source metadata and search."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from .connection import Database


@dataclass(frozen=True)
class CandidateSource:
    id: str
    path: str
    source_type: str
    title: str
    approved: bool
    source: str
    topics: tuple[str, ...]
    content: str
    content_hash: str
    last_indexed_at: str

    @property
    def snippet(self) -> str:
        compact = " ".join(self.content.split())
        return compact if len(compact) <= 240 else f"{compact[:237]}..."


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class CandidateSourceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(
        self,
        *,
        source_id: str,
        path: str,
        source_type: str,
        title: str,
        approved: bool,
        source: str,
        topics: Iterable[str],
        content: str,
    ) -> None:
        topics_tuple = tuple(str(topic) for topic in topics)
        indexed_at = datetime.now(UTC).isoformat()
        digest = content_hash(content)
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO candidate_sources(
                    id, path, source_type, title, approved, source,
                    topics_json, content, content_hash, last_indexed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path=excluded.path,
                    source_type=excluded.source_type,
                    title=excluded.title,
                    approved=excluded.approved,
                    source=excluded.source,
                    topics_json=excluded.topics_json,
                    content=excluded.content,
                    content_hash=excluded.content_hash,
                    last_indexed_at=excluded.last_indexed_at
                """,
                (
                    source_id,
                    path,
                    source_type,
                    title,
                    int(approved),
                    source,
                    json.dumps(topics_tuple),
                    content,
                    digest,
                    indexed_at,
                ),
            )
            if self._fts_available(connection):
                connection.execute(
                    "DELETE FROM candidate_sources_fts WHERE source_id = ?", (source_id,)
                )
                connection.execute(
                    """
                    INSERT INTO candidate_sources_fts(source_id, title, topics, content)
                    VALUES (?, ?, ?, ?)
                    """,
                    (source_id, title, " ".join(topics_tuple), content),
                )

    def get(self, source_id: str) -> CandidateSource | None:
        self.database.migrate()
        with self.database.session() as connection:
            row = connection.execute(
                "SELECT * FROM candidate_sources WHERE id = ?", (source_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def count(self) -> int:
        self.database.migrate()
        with self.database.session() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM candidate_sources").fetchone()[0])

    def remove_missing_markdown_paths(self, current_paths: Iterable[str]) -> int:
        """Remove indexed Markdown documents that no longer exist on disk."""

        current = tuple(current_paths)
        self.database.migrate()
        with self.database.session() as connection:
            stale_rows = connection.execute(
                """
                SELECT id FROM candidate_sources
                WHERE source_type != 'fact' AND path LIKE 'candidate/%'
                  AND path NOT IN ({})
                """.format(",".join("?" for _ in current) or "''"),
                current,
            ).fetchall()
            stale_ids = [row["id"] for row in stale_rows]
            if not stale_ids:
                return 0
            if self._fts_available(connection):
                placeholders = ",".join("?" for _ in stale_ids)
                connection.execute(
                    f"DELETE FROM candidate_sources_fts WHERE source_id IN ({placeholders})",
                    stale_ids,
                )
            placeholders = ",".join("?" for _ in stale_ids)
            connection.execute(
                f"DELETE FROM candidate_sources WHERE id IN ({placeholders})", stale_ids
            )
            return len(stale_ids)

    def search(
        self, query: str, *, source_types: Iterable[str] | None = None, top_k: int = 5
    ) -> list[CandidateSource]:
        """Search indexed candidate knowledge using FTS5 with a LIKE fallback."""

        self.database.migrate()
        tokens = re.findall(r"[\w-]+", query.casefold())
        if not tokens:
            return []
        normalized_types = tuple(source_types or ())
        limit = max(1, min(top_k, 100))
        with self.database.session() as connection:
            type_clause = ""
            params: list[object] = []
            if normalized_types:
                placeholders = ",".join("?" for _ in normalized_types)
                type_clause = f" AND s.source_type IN ({placeholders})"
                params.extend(normalized_types)

            rows = []
            if self._fts_available(connection):
                fts_query = " OR ".join(f'"{token}"*' for token in tokens)
                rows = connection.execute(
                    f"""
                    SELECT s.*
                    FROM candidate_sources_fts f
                    JOIN candidate_sources s ON s.id = f.source_id
                    WHERE candidate_sources_fts MATCH ?{type_clause}
                    ORDER BY rank
                    LIMIT ?
                    """,
                    [fts_query, *params, limit],
                ).fetchall()

            if not rows:
                where = " AND ".join(
                    "LOWER(s.title || ' ' || s.content || ' ' || s.topics_json) LIKE ?"
                    for _ in tokens
                )
                like_params = [f"%{token}%" for token in tokens]
                rows = connection.execute(
                    f"""
                    SELECT s.*
                    FROM candidate_sources s
                    WHERE {where}{type_clause}
                    ORDER BY s.approved DESC, s.last_indexed_at DESC
                    LIMIT ?
                    """,
                    [*like_params, *params, limit],
                ).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _fts_available(connection) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'candidate_sources_fts'"
        ).fetchone()
        return row is not None

    @staticmethod
    def _from_row(row) -> CandidateSource:
        topics = tuple(json.loads(row["topics_json"] or "[]"))
        return CandidateSource(
            id=row["id"],
            path=row["path"],
            source_type=row["source_type"],
            title=row["title"],
            approved=bool(row["approved"]),
            source=row["source"],
            topics=topics,
            content=row["content"],
            content_hash=row["content_hash"],
            last_indexed_at=row["last_indexed_at"],
        )

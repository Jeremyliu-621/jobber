"""Persistence for source-grounded opportunity documents."""

from __future__ import annotations

import json

from job_agent.models import OpportunityDocument

from .connection import Database


class OpportunityRepository:
    """Store the latest structured extraction for each normalized job."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def upsert(self, document: OpportunityDocument) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            connection.execute(
                """
                INSERT INTO opportunities(
                    id, job_id, source_hash, extractor_version, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    source_hash=excluded.source_hash,
                    extractor_version=excluded.extractor_version,
                    payload_json=excluded.payload_json,
                    last_updated_at=CURRENT_TIMESTAMP
                """,
                (
                    f"opportunity.{document.job_id}",
                    document.job_id,
                    document.source_hash,
                    document.extractor_version,
                    document.model_dump_json(),
                ),
            )

    def get(self, job_id: str) -> OpportunityDocument | None:
        self.database.migrate()
        with self.database.session() as connection:
            row = connection.execute(
                "SELECT payload_json FROM opportunities WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return OpportunityDocument.model_validate(json.loads(row["payload_json"]))

    def count(self) -> int:
        self.database.migrate()
        with self.database.session() as connection:
            row = connection.execute("SELECT COUNT(*) FROM opportunities").fetchone()
        return int(row[0])

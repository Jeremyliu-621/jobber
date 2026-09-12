"""Small SQLite database wrapper with migration support."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    """SQLite connection manager for the application database."""

    def __init__(self, path: Path, migration_dir: Path | None = None) -> None:
        self.path = Path(path)
        self.migration_dir = migration_dir or Path(__file__).resolve().parents[3] / "migrations"

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> int:
        """Apply each unapplied SQL migration in filename order."""

        with self.session() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            applied = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                )
            }
            for migration_path in sorted(self.migration_dir.glob("*.sql")):
                try:
                    version = int(migration_path.stem.split("_", 1)[0])
                except ValueError as error:
                    raise ValueError(
                        f"Migration filename must start with an integer: {migration_path.name}"
                    ) from error
                if version in applied:
                    continue
                connection.executescript(migration_path.read_text(encoding="utf-8"))
                connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()
            return int(row["version"])

    def status(self) -> dict[str, int | str]:
        """Return a compact, read-only status snapshot for the CLI."""

        version = self.migrate()
        with self.session() as connection:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            source_count = connection.execute("SELECT COUNT(*) FROM candidate_sources").fetchone()[
                0
            ]
            job_count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            application_count = connection.execute(
                "SELECT COUNT(*) FROM applications"
            ).fetchone()[0]
            resume_count = connection.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
        return {
            "path": str(self.path),
            "migration_version": version,
            "journal_mode": str(journal_mode),
            "candidate_sources": int(source_count),
            "jobs": int(job_count),
            "applications": int(application_count),
            "resumes": int(resume_count),
        }

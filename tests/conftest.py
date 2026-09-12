from pathlib import Path

import pytest

from job_agent.db import Database


@pytest.fixture
def migration_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture
def database(tmp_path: Path, migration_dir: Path) -> Database:
    return Database(tmp_path / "data.sqlite3", migration_dir=migration_dir)

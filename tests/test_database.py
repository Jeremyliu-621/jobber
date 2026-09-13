def test_migrations_enable_wal_and_create_core_tables(database) -> None:
    status = database.status()

    assert status["migration_version"] == 3
    assert status["journal_mode"].lower() == "wal"
    assert status["candidate_sources"] == 0

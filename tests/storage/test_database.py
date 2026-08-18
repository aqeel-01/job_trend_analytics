"""Tests for database initialization and schema."""

from pipeline.storage.schema import REQUIRED_TABLES, SCHEMA_VERSION


def test_database_initialization(database) -> None:
    assert database.schema_version() == SCHEMA_VERSION
    assert database.has_required_tables()
    assert set(REQUIRED_TABLES).issubset(database.table_names())


def test_initialize_is_idempotent(database) -> None:
    database.initialize()
    database.initialize()
    assert database.schema_version() == SCHEMA_VERSION
    assert database.has_required_tables()

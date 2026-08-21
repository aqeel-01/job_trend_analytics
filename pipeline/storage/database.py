"""SQLite database connection and schema initialization."""

import sqlite3
from pathlib import Path

from pipeline.storage.schema import (
    COLUMN_MIGRATIONS_V2,
    MIGRATIONS,
    REQUIRED_TABLES,
    SCHEMA_MIGRATIONS_TABLE,
    SCHEMA_VERSION,
)


class Database:
    """Manage SQLite connections and apply V1 schema migrations."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._connection: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Open (or return) the database connection."""
        if self._connection is None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(self.database_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
        return self._connection

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def initialize(self) -> None:
        """Create schema and apply pending migrations."""
        conn = self.connect()
        conn.execute(SCHEMA_MIGRATIONS_TABLE)
        current_version = self._get_schema_version(conn)

        if current_version is None:
            for version in sorted(MIGRATIONS):
                conn.executescript(MIGRATIONS[version])
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)",
                    (version,),
                )
            self._apply_column_migrations(conn, COLUMN_MIGRATIONS_V2)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (2,),
            )
            conn.commit()
            return

        for version in sorted(MIGRATIONS):
            if version <= current_version:
                continue
            conn.executescript(MIGRATIONS[version])
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )

        if current_version < 2:
            self._apply_column_migrations(conn, COLUMN_MIGRATIONS_V2)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (2,),
            )

        conn.commit()

    def schema_version(self) -> int | None:
        """Return the applied schema version, if initialized."""
        conn = self.connect()
        return self._get_schema_version(conn)

    def table_names(self) -> set[str]:
        """Return user table names present in the database."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {row["name"] for row in rows}

    def has_required_tables(self) -> bool:
        """Return True when all V1 tables exist."""
        return set(REQUIRED_TABLES).issubset(self.table_names())

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row["name"] for row in rows}

    def _apply_column_migrations(
        self,
        conn: sqlite3.Connection,
        migrations: tuple[tuple[str, str, str], ...],
    ) -> None:
        """Add missing columns idempotently (safe for early V1 databases)."""
        existing_tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table, column, definition in migrations:
            if table not in existing_tables:
                continue
            existing = self._table_columns(conn, table)
            if column in existing:
                continue
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            if table == "pipeline_runs" and column == "created_at":
                conn.execute(
                    """
                    UPDATE pipeline_runs
                    SET created_at = COALESCE(started_at, datetime('now'))
                    WHERE created_at IS NULL
                    """
                )

    @staticmethod
    def _get_schema_version(conn: sqlite3.Connection) -> int | None:
        row = conn.execute(
            "SELECT MAX(version) AS version FROM schema_migrations"
        ).fetchone()
        if row is None or row["version"] is None:
            return None
        return int(row["version"])

    @property
    def target_schema_version(self) -> int:
        """Latest schema version defined for V1."""
        return SCHEMA_VERSION

"""
File: migrations.py
Path: src/persistence/migrations.py
Role: Lightweight recorded SQLite migrations for module-owned persistence schemas.
Used By:
 - src/persistence/adapters/sqlite.py
 - src/persistence/adapters/sqlite_audit.py
Depends On:
 - dataclasses
 - sqlite3
Notes:
 - This is a small migration registry for the modular-monolith transition, not a full external migration framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class SQLiteMigration:
    migration_id: str
    statements: tuple[str, ...]


def apply_sqlite_migrations(connection: sqlite3.Connection, migrations: list[SQLiteMigration]) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id TEXT NOT NULL PRIMARY KEY,
            applied_at_utc TEXT NOT NULL
        )
        """
    )
    existing = {
        str(row[0])
        for row in connection.execute("SELECT migration_id FROM schema_migrations ORDER BY migration_id").fetchall()
    }
    for migration in migrations:
        if migration.migration_id in existing:
            continue
        for statement in migration.statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations (migration_id, applied_at_utc) VALUES (?, ?)",
            (migration.migration_id, _utc_now()),
        )
    connection.commit()

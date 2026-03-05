"""
File: local_data_safety.py
Path: scripts/release/local_data_safety.py
Role: Backup, restore, and validate local runtime SQLite data safely.
Used By:
 - Makefile
 - operators running local recovery drills
Depends On:
 - sqlite3
 - argparse
 - pathlib
 - hashlib
Notes:
 - Defaults target `.exo_data/exo.db` unless `EXO_DB_PATH` is set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


REQUIRED_TABLES: tuple[str, ...] = (
    "sessions",
    "checkpoints",
    "tools",
    "agents",
    "api_keys",
    "providers",
    "tool_versions",
    "byoc_jobs",
    "byoc_result_idempotency",
    "byoc_result_payloads",
    "byoc_replay_guard",
)


def _default_db_path() -> Path:
    return Path(os.environ.get("EXO_DB_PATH", ".exo_data/exo.db"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _backup(db_path: Path, out_path: Path, meta_out: Path | None) -> int:
    if not db_path.exists():
        print(f"DB backup failed: source does not exist: {db_path}")
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, out_path)
    payload = {
        "operation": "backup",
        "db_path": str(db_path),
        "backup_path": str(out_path),
        "sha256": _sha256(out_path),
        "size_bytes": out_path.stat().st_size,
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    _write_json(meta_out, payload)
    print(f"DB backup written: {out_path}")
    return 0


def _latest_backup_path(backup_dir: Path) -> Path | None:
    if not backup_dir.exists():
        return None
    backups = [entry for entry in backup_dir.glob("*.db") if entry.is_file()]
    if not backups:
        return None
    backups.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return backups[0]


def _restore(in_path: Path, db_path: Path, force: bool, meta_out: Path | None) -> int:
    if not in_path.exists():
        print(f"DB restore failed: backup does not exist: {in_path}")
        return 1
    if db_path.exists() and not force:
        print(f"DB restore blocked: target exists ({db_path}). Use --force to overwrite.")
        return 1
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(in_path, db_path)
    payload = {
        "operation": "restore",
        "backup_path": str(in_path),
        "db_path": str(db_path),
        "sha256": _sha256(db_path),
        "size_bytes": db_path.stat().st_size,
        "restored_at_utc": datetime.now(UTC).isoformat(),
    }
    _write_json(meta_out, payload)
    print(f"DB restored to: {db_path}")
    return 0


def _validate(db_path: Path, meta_out: Path | None) -> int:
    if not db_path.exists():
        print(f"DB validation failed: target does not exist: {db_path}")
        return 1
    with sqlite3.connect(str(db_path)) as conn:
        integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
        integrity = str(integrity_row[0]) if integrity_row else "failed"
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name ASC"
        ).fetchall()
    tables = [str(row[0]) for row in table_rows]
    missing = sorted(set(REQUIRED_TABLES) - set(tables))
    ok = integrity == "ok" and not missing
    payload = {
        "operation": "validate",
        "db_path": str(db_path),
        "integrity_check": integrity,
        "required_tables_count": len(REQUIRED_TABLES),
        "tables_count": len(tables),
        "missing_required_tables": missing,
        "validated_at_utc": datetime.now(UTC).isoformat(),
        "ok": ok,
    }
    _write_json(meta_out, payload)
    if not ok:
        print("DB validation failed.")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    print(f"DB validation passed: {db_path}")
    return 0


def _timestamped_backup_path(backup_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return backup_dir / f"exo-db-backup-{timestamp}.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Local SQLite data safety helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create a DB backup.")
    backup_parser.add_argument("--db", default=str(_default_db_path()), help="Source SQLite DB path.")
    backup_parser.add_argument("--out", default="", help="Backup output path.")
    backup_parser.add_argument(
        "--backup-dir",
        default=".local/db-backups",
        help="Backup directory when --out is not provided.",
    )
    backup_parser.add_argument("--meta-out", default="", help="Optional JSON metadata output path.")

    restore_parser = subparsers.add_parser("restore", help="Restore DB from backup.")
    restore_parser.add_argument("--in", dest="in_path", default="", help="Backup input path.")
    restore_parser.add_argument("--db", default=str(_default_db_path()), help="Restore target DB path.")
    restore_parser.add_argument(
        "--backup-dir",
        default=".local/db-backups",
        help="Backup directory used when --in is not provided (latest backup).",
    )
    restore_parser.add_argument("--force", action="store_true", help="Overwrite existing DB path.")
    restore_parser.add_argument("--meta-out", default="", help="Optional JSON metadata output path.")

    validate_parser = subparsers.add_parser("validate", help="Validate DB integrity and required schema.")
    validate_parser.add_argument("--db", default=str(_default_db_path()), help="SQLite DB path.")
    validate_parser.add_argument("--meta-out", default="", help="Optional JSON metadata output path.")

    args = parser.parse_args()
    if args.command == "backup":
        db_path = Path(args.db)
        out_path = Path(args.out) if args.out else _timestamped_backup_path(Path(args.backup_dir))
        meta_out = Path(args.meta_out) if args.meta_out else None
        return _backup(db_path, out_path, meta_out)

    if args.command == "restore":
        db_path = Path(args.db)
        if args.in_path:
            in_path = Path(args.in_path)
        else:
            latest = _latest_backup_path(Path(args.backup_dir))
            if latest is None:
                print(f"DB restore failed: no backup found in {args.backup_dir}")
                return 1
            in_path = latest
        meta_out = Path(args.meta_out) if args.meta_out else None
        return _restore(in_path, db_path, bool(args.force), meta_out)

    if args.command == "validate":
        db_path = Path(args.db)
        meta_out = Path(args.meta_out) if args.meta_out else None
        return _validate(db_path, meta_out)

    print("Unknown command.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

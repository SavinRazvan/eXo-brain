"""
File: test_tool_version_store.py
Path: tests/modules/persistence/test_tool_version_store.py
Role: Unit tests for SQLiteToolVersionStore persistence behavior.
Used By:
 - pytest
Depends On:
 - src/persistence/adapters/sqlite.py
 - src/persistence/contracts.py
Notes:
 - Uses in-memory SQLite for deterministic fast tests.
"""

from __future__ import annotations

import asyncio

from src.persistence.adapters.sqlite import SQLiteToolVersionStore
from src.persistence.contracts import (
    ToolPackageManifest,
    ToolValidationResult,
    ToolValidationState,
    ToolVersionRecord,
)


def _record(version: str, active: bool = False) -> ToolVersionRecord:
    return ToolVersionRecord(
        tenant_id="t1",
        tool_name="calculate_result",
        version=version,
        manifest=ToolPackageManifest(
            tool_name="calculate_result",
            version=version,
            input_schema={"type": "object"},
        ),
        validation=ToolValidationResult(
            tool_name="calculate_result",
            version=version,
            state=ToolValidationState.VALID,
            normalized_schema_hash=f"hash-{version}",
        ),
        package_ref=f"pkg:{version}",
        active=active,
        created_at=f"2026-01-01T00:00:0{version}Z",
    )


def test_save_get_and_list_versions() -> None:
    store = SQLiteToolVersionStore(":memory:")

    async def run() -> None:
        await store.save_tool_version(_record("1"))
        await store.save_tool_version(_record("2"))
        one = await store.get_tool_version("t1", "calculate_result", "1")
        assert one is not None
        assert one.package_ref == "pkg:1"
        versions = await store.list_tool_versions("t1", "calculate_result")
        assert len(versions) == 2

    asyncio.run(run())


def test_set_active_version_marks_one_active() -> None:
    store = SQLiteToolVersionStore(":memory:")

    async def run() -> None:
        await store.save_tool_version(_record("1"))
        await store.save_tool_version(_record("2"))
        await store.set_active_tool_version("t1", "calculate_result", "2")
        active = await store.get_active_tool_version("t1", "calculate_result")
        assert active is not None
        assert active.version == "2"
        all_versions = await store.list_tool_versions("t1", "calculate_result")
        assert len([v for v in all_versions if v.active]) == 1

    asyncio.run(run())

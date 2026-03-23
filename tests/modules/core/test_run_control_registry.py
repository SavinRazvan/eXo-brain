"""
File: test_run_control_registry.py
Path: tests/modules/core/test_run_control_registry.py
Role: Unit tests for in-memory RunControlRegistry lifecycle and query APIs.
Used By:
 - pytest
Depends On:
 - src/core/run_control_registry.py
Notes:
 - Complements SQLite-backed coverage in test_shared_state_backends.py.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from src.core.run_control_registry import RunControlRegistry, RunControlRecord, SQLiteRunControlRegistry


def test_start_run_stores_record_and_uses_run_id_as_correlation_fallback() -> None:
    reg = RunControlRegistry()
    rec = reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="",
        transport="ws",
    )
    assert isinstance(rec, RunControlRecord)
    assert rec.correlation_id == "r1"
    got = reg.get_run(tenant_id="t1", run_id="r1")
    assert got is not None
    assert got["transport"] == "ws"
    assert got["status"] == "running"


def test_record_tool_call_rejects_blank_and_unknown_run() -> None:
    reg = RunControlRegistry()
    reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    assert reg.record_tool_call(tenant_id="t1", run_id="r1", call_id="  ") is False
    assert reg.record_tool_call(tenant_id="t1", run_id="missing", call_id="x") is False


def test_mark_terminal_returns_false_for_unknown_run() -> None:
    reg = RunControlRegistry()
    assert (
        reg.mark_terminal(
            tenant_id="t1",
            run_id="nope",
            status="completed",
            terminal_event="done",
        )
        is False
    )


def test_request_cancel_returns_false_for_unknown_run() -> None:
    reg = RunControlRegistry()
    assert reg.request_cancel(tenant_id="t1", run_id="nope", reason="x") is False


def test_get_run_returns_none_for_unknown() -> None:
    reg = RunControlRegistry()
    assert reg.get_run(tenant_id="t1", run_id="r1") is None


def test_request_cancel_leaves_terminal_status_unchanged() -> None:
    reg = RunControlRegistry()
    reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    reg.mark_terminal(
        tenant_id="t1",
        run_id="r1",
        status="completed",
        terminal_event="finished",
        terminal_message="ok",
    )
    assert reg.request_cancel(tenant_id="t1", run_id="r1", reason="late")
    record = reg.get_run(tenant_id="t1", run_id="r1")
    assert record is not None
    assert record["status"] == "completed"
    assert record["cancel_requested"] is True


def test_list_runs_sorts_by_updated_and_clamps_limit() -> None:
    reg = RunControlRegistry()
    reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r_old",
        correlation_id="c1",
        transport="sse",
    )
    reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r_new",
        correlation_id="c2",
        transport="sse",
    )
    reg.record_tool_call(tenant_id="t1", run_id="r_old", call_id="touch")
    rows = reg.list_runs(tenant_id="t1", limit=1)
    assert len(rows) == 1
    assert rows[0]["run_id"] == "r_old"


def test_list_runs_limit_zero_becomes_one() -> None:
    reg = RunControlRegistry()
    reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    assert len(reg.list_runs(tenant_id="t1", limit=0)) == 1


def test_call_ids_for_run_empty_when_missing() -> None:
    reg = RunControlRegistry()
    assert reg.call_ids_for_run(tenant_id="t1", run_id="x") == []


def test_count_active_runs_excludes_completed() -> None:
    reg = RunControlRegistry()
    reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    assert reg.count_active_runs(tenant_id="t1") == 1
    reg.mark_terminal(
        tenant_id="t1",
        run_id="r1",
        status="completed",
        terminal_event="done",
    )
    assert reg.count_active_runs(tenant_id="t1") == 0


def test_run_control_record_to_dict_sorts_call_ids() -> None:
    rec = RunControlRecord(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    rec.call_ids.update({"b", "a"})
    d = rec.to_dict()
    assert d["call_ids"] == ["a", "b"]


def test_sqlite_registry_record_and_mark_fail_when_run_missing(tmp_path: Path) -> None:
    db = SQLiteRunControlRegistry(str(tmp_path / "rc.db"))
    assert db.record_tool_call(tenant_id="t1", run_id="ghost", call_id="c1") is False
    assert (
        db.mark_terminal(
            tenant_id="t1",
            run_id="ghost",
            status="completed",
            terminal_event="x",
        )
        is False
    )
    assert db.request_cancel(tenant_id="t1", run_id="ghost", reason="n") is False


def test_sqlite_registry_call_ids_and_list_runs_empty(tmp_path: Path) -> None:
    db = SQLiteRunControlRegistry(str(tmp_path / "rc.db"))
    assert db.call_ids_for_run(tenant_id="t1", run_id="r1") == []
    assert db.list_runs(tenant_id="t1") == []
    assert db.count_active_runs(tenant_id="t1") == 0


def test_sqlite_registry_list_runs_respects_limit_and_order(tmp_path: Path) -> None:
    db = SQLiteRunControlRegistry(str(tmp_path / "rc.db"))
    db.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    db.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r2",
        correlation_id="c2",
        transport="sse",
    )
    db.record_tool_call(tenant_id="t1", run_id="r1", call_id="bump")
    limited = db.list_runs(tenant_id="t1", limit=1)
    assert len(limited) == 1
    assert limited[0]["run_id"] == "r1"


def test_sqlite_registry_record_tool_call_rejects_blank_call_id(tmp_path: Path) -> None:
    db = SQLiteRunControlRegistry(str(tmp_path / "rc.db"))
    db.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    assert db.record_tool_call(tenant_id="t1", run_id="r1", call_id="  ") is False
    assert db.record_tool_call(tenant_id="t1", run_id="r1", call_id="c99") is True
    assert db.call_ids_for_run(tenant_id="t1", run_id="r1") == ["c99"]


def test_memory_registry_prunes_oldest_terminal_runs_per_cap() -> None:
    reg = RunControlRegistry(max_terminal_records_per_tenant=1)
    reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    reg.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r2",
        correlation_id="c2",
        transport="sse",
    )
    assert reg.mark_terminal(
        tenant_id="t1",
        run_id="r1",
        status="completed",
        terminal_event="a",
    )
    assert reg.mark_terminal(
        tenant_id="t1",
        run_id="r2",
        status="completed",
        terminal_event="b",
    )
    assert reg.get_run(tenant_id="t1", run_id="r1") is None
    assert reg.get_run(tenant_id="t1", run_id="r2") is not None


def test_sqlite_registry_prunes_oldest_terminal_runs_per_cap(tmp_path: Path) -> None:
    db = SQLiteRunControlRegistry(str(tmp_path / "rc.db"), max_terminal_records_per_tenant=1)
    db.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    db.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r2",
        correlation_id="c2",
        transport="sse",
    )
    assert db.mark_terminal(
        tenant_id="t1",
        run_id="r1",
        status="completed",
        terminal_event="a",
    )
    assert db.mark_terminal(
        tenant_id="t1",
        run_id="r2",
        status="completed",
        terminal_event="b",
    )
    assert db.get_run(tenant_id="t1", run_id="r1") is None
    assert db.get_run(tenant_id="t1", run_id="r2") is not None


def test_sqlite_registry_count_active_runs_returns_zero_when_fetchone_is_none(tmp_path: Path) -> None:
    db = SQLiteRunControlRegistry(str(tmp_path / "rc.db"))
    mock_conn = MagicMock()
    cursor = MagicMock()
    mock_conn.execute.return_value = cursor
    cursor.fetchone.return_value = None
    mock_conn.__enter__ = lambda self: mock_conn
    mock_conn.__exit__ = lambda *args: None

    original_conn = db._conn

    def _patched_conn() -> MagicMock:
        return mock_conn

    db._conn = _patched_conn  # type: ignore[method-assign]
    try:
        assert db.count_active_runs(tenant_id="t1") == 0
    finally:
        db._conn = original_conn  # type: ignore[method-assign]

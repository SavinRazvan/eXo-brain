"""
File: test_shared_state_backends.py
Path: tests/modules/core/test_shared_state_backends.py
Role: Validate shared-state backend primitives for Option C multi-instance patterns.
Used By:
 - CI test suite
Depends On:
 - src/core/run_control_registry.py
 - src/tenancy/rate_limiter.py
 - src/policies/byoc_fairness.py
Notes:
 - Tests focus on deterministic behavior and API compatibility with in-memory backends.
"""

from __future__ import annotations

from pathlib import Path

from src.core.run_control_registry import SQLiteRunControlRegistry
from src.policies.byoc_fairness import SQLiteByocFairAdmissionCoordinator
from src.tenancy.rate_limiter import SQLiteTenantRateLimiter


def test_sqlite_run_control_registry_roundtrip(tmp_path: Path) -> None:
    registry = SQLiteRunControlRegistry(str(tmp_path / "state.db"))
    registry.start_run(
        tenant_id="t1",
        session_id="s1",
        run_id="r1",
        correlation_id="c1",
        transport="sse",
    )
    assert registry.record_tool_call(tenant_id="t1", run_id="r1", call_id="tc1")
    assert registry.request_cancel(tenant_id="t1", run_id="r1", reason="operator")
    record = registry.get_run(tenant_id="t1", run_id="r1")
    assert record is not None
    assert record["cancel_requested"] is True
    assert "tc1" in record["call_ids"]
    assert registry.count_active_runs(tenant_id="t1") == 1
    assert registry.mark_terminal(
        tenant_id="t1",
        run_id="r1",
        status="cancelled",
        terminal_event="test_terminal",
    )
    assert registry.count_active_runs(tenant_id="t1") == 0


def test_sqlite_rate_limiter_enforces_window(tmp_path: Path) -> None:
    limiter = SQLiteTenantRateLimiter(
        db_path=str(tmp_path / "state.db"),
        max_requests=2,
        window_seconds=60,
    )
    assert limiter.allow("t1")[0] is True
    assert limiter.allow("t1")[0] is True
    allowed, retry = limiter.allow("t1")
    assert allowed is False
    assert retry == 60


def test_sqlite_fair_admission_acquire_release(tmp_path: Path) -> None:
    coordinator = SQLiteByocFairAdmissionCoordinator(
        db_path=str(tmp_path / "state.db"),
        max_inflight_global=1,
        lease_seconds=5,
    )
    token = coordinator.acquire(tenant_id="t1", wait_timeout_ms=25)
    assert token is not None
    token2 = coordinator.acquire(tenant_id="t2", wait_timeout_ms=10)
    assert token2 is None
    coordinator.release(token)
    token3 = coordinator.acquire(tenant_id="t2", wait_timeout_ms=25)
    assert token3 is not None

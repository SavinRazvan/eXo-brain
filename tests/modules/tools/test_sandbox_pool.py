"""
File: test_sandbox_pool.py
Path: tests/modules/tools/test_sandbox_pool.py
Role: Unit tests for tenant sandbox pool lifecycle (create/reuse/evict).
Used By:
 - pytest
Depends On:
 - src/tools/sandbox/pool.py
Notes:
 - Verifies in-memory tenant worker lifecycle semantics.
"""

from __future__ import annotations

from src.tools.sandbox.pool import TenantSandboxPool


def test_pool_reuses_worker_for_same_tenant() -> None:
    pool = TenantSandboxPool(max_workers_per_tenant=1)
    first = pool.acquire("t1")
    second = pool.acquire("t1")
    assert first is second
    assert pool.stats()["tenants"] == 1
    pool.close()


def test_pool_isolates_workers_per_tenant() -> None:
    pool = TenantSandboxPool(max_workers_per_tenant=1)
    first = pool.acquire("t1")
    second = pool.acquire("t2")
    assert first is not second
    assert pool.stats()["tenants"] == 2
    pool.close()


def test_pool_evict_tenant_recreates_new_worker_on_next_acquire() -> None:
    pool = TenantSandboxPool(max_workers_per_tenant=1)
    first = pool.acquire("t1")
    evicted = pool.evict_tenant("t1")
    assert evicted is True
    second = pool.acquire("t1")
    assert first is not second
    pool.close()


def test_pool_evicts_lru_tenant_when_capacity_reached() -> None:
    pool = TenantSandboxPool(max_workers_per_tenant=1, max_tenants=2)
    first = pool.acquire("t1")
    _ = first
    second = pool.acquire("t2")
    _ = second
    # Touch t2 last so t1 becomes LRU.
    pool.acquire("t2")
    pool.acquire("t3")
    assert pool.stats()["tenants"] == 2
    # t1 should have been evicted due to LRU capacity policy.
    assert pool.evict_tenant("t1") is False
    assert pool.evict_tenant("t2") is True
    assert pool.evict_tenant("t3") is True
    pool.close()


def test_pool_evict_idle_removes_only_stale_tenants() -> None:
    now = {"value": 0.0}

    def _clock() -> float:
        return now["value"]

    pool = TenantSandboxPool(max_workers_per_tenant=1, clock=_clock)
    pool.acquire("t1")  # at 0.0
    now["value"] = 10.0
    pool.acquire("t2")  # at 10.0

    evicted = pool.evict_idle(max_idle_seconds=5.0)
    assert evicted == ["t1"]
    assert pool.stats()["tenants"] == 1
    assert pool.stats()["evicted_workers_idle"] == 1
    events = pool.cleanup_events()
    assert events[-1]["tenant_id"] == "t1"
    assert events[-1]["reason"] == "idle_ttl"
    pool.close()


def test_pool_cleanup_stats_include_capacity_and_explicit_evictions() -> None:
    pool = TenantSandboxPool(max_workers_per_tenant=1, max_tenants=1)
    pool.acquire("t1")
    pool.acquire("t2")  # triggers capacity LRU eviction of t1
    assert pool.stats()["evicted_workers_capacity"] == 1
    assert pool.evict_tenant("t2", reason="explicit") is True
    assert pool.stats()["evicted_workers_explicit"] == 1
    events = pool.cleanup_events(limit=5)
    reasons = [entry["reason"] for entry in events]
    assert "capacity_lru" in reasons
    assert "explicit" in reasons
    pool.close()

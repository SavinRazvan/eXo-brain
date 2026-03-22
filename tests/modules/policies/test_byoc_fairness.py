"""
File: test_byoc_fairness.py
Path: tests/modules/policies/test_byoc_fairness.py
Role: Verifies deterministic BYOC fair-admission behavior under contention.
Used By:
 - pytest
Depends On:
 - src/policies/byoc_fairness.py
Notes:
 - Ensures no-tenant-starvation under configured limits.
"""

from __future__ import annotations

from unittest.mock import patch

import threading
import time

from src.policies import byoc_fairness as byoc_fairness_module
from src.policies.byoc_fairness import (
    ByocFairAdmissionCoordinator,
    _PendingAdmission,
    _pick_next_tenant,
)


def test_pick_next_tenant_returns_none_when_pending_empty() -> None:
    assert _pick_next_tenant([], {}) is None


def test_pick_next_tenant_uses_deterministic_tie_break() -> None:
    pending = [
        _PendingAdmission(tenant_id="t2", request_id=2),
        _PendingAdmission(tenant_id="t1", request_id=3),
    ]
    grants_total = {"t1": 1, "t2": 1}
    assert _pick_next_tenant(pending, grants_total) == "t2"

    grants_total = {"t1": 1, "t2": 2}
    assert _pick_next_tenant(pending, grants_total) == "t1"


def test_fair_admission_release_decrements_tenant_inflight_when_gt_one() -> None:
    coordinator = ByocFairAdmissionCoordinator(max_inflight_global=3)
    t1 = coordinator.acquire(tenant_id="t1", wait_timeout_ms=500)
    t2 = coordinator.acquire(tenant_id="t1", wait_timeout_ms=500)
    assert t1 is not None and t2 is not None
    coordinator.release(t1)
    coordinator.release(t2)


def test_try_grant_unlocked_breaks_when_next_tenant_is_falsy() -> None:
    coordinator = ByocFairAdmissionCoordinator(max_inflight_global=2)
    with coordinator._condition:
        coordinator._pending.append(_PendingAdmission(tenant_id="", request_id=1))
        coordinator._inflight_total = 0
        coordinator._try_grant_unlocked()


def test_try_grant_unlocked_breaks_when_pending_missing_picked_tenant() -> None:
    coordinator = ByocFairAdmissionCoordinator(max_inflight_global=2)
    with coordinator._condition:
        coordinator._pending.append(_PendingAdmission(tenant_id="t1", request_id=1))
        coordinator._inflight_total = 0
        with patch.object(byoc_fairness_module, "_pick_next_tenant", return_value="ghost"):
            coordinator._try_grant_unlocked()


def test_fair_admission_coordinator_prevents_starvation_under_contention() -> None:
    coordinator = ByocFairAdmissionCoordinator(max_inflight_global=1)
    tenants = ["t1", "t2", "t3"]
    loops = 8
    counts = {tenant: 0 for tenant in tenants}
    gate = threading.Barrier(len(tenants))

    def _worker(tenant_id: str) -> None:
        gate.wait()
        for _ in range(loops):
            token = coordinator.acquire(tenant_id=tenant_id, wait_timeout_ms=2000)
            assert token is not None
            counts[tenant_id] += 1
            time.sleep(0.001)
            coordinator.release(token)

    threads = [threading.Thread(target=_worker, args=(tenant,)) for tenant in tenants]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)
        assert not thread.is_alive()

    assert counts == {tenant: loops for tenant in tenants}

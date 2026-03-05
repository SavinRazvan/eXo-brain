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

import threading
import time

from src.policies.byoc_fairness import (
    ByocFairAdmissionCoordinator,
    _PendingAdmission,
    _pick_next_tenant,
)


def test_pick_next_tenant_uses_deterministic_tie_break() -> None:
    pending = [
        _PendingAdmission(tenant_id="t2", request_id=2),
        _PendingAdmission(tenant_id="t1", request_id=3),
    ]
    grants_total = {"t1": 1, "t2": 1}
    assert _pick_next_tenant(pending, grants_total) == "t2"

    grants_total = {"t1": 1, "t2": 2}
    assert _pick_next_tenant(pending, grants_total) == "t1"


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

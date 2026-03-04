"""
File: pool.py
Path: src/tools/sandbox/pool.py
Role: Manage per-tenant hosted sandbox runtime workers (create/reuse/evict).
Used By:
 - src/tools/sandbox/runtime.py
 - src/runtime/tenant_runtime.py
Depends On:
 - concurrent.futures
 - dataclasses
 - threading
Notes:
 - This pool is in-memory and process-local.
 - Each tenant currently maps to a single worker executor.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import threading
from time import monotonic
from typing import Callable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TenantSandboxWorker:
    """One hosted sandbox worker allocation for a tenant."""

    tenant_id: str
    executor: ThreadPoolExecutor
    created_at_utc: str
    last_used_at_utc: str
    last_used_monotonic: float
    execution_count: int = 0


@dataclass(slots=True)
class WorkerCleanupEvent:
    tenant_id: str
    reason: str
    timestamp_utc: str


class TenantSandboxPool:
    """Create/reuse/evict per-tenant sandbox workers."""

    def __init__(
        self,
        max_workers_per_tenant: int = 1,
        max_tenants: int | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._max_workers_per_tenant = max(1, int(max_workers_per_tenant))
        self._max_tenants = max_tenants if max_tenants is None else max(1, int(max_tenants))
        self._workers: dict[str, TenantSandboxWorker] = {}
        self._lock = threading.Lock()
        self._clock = clock or monotonic
        self._created_workers = 0
        self._evicted_workers_total = 0
        self._evicted_workers_explicit = 0
        self._evicted_workers_idle = 0
        self._evicted_workers_capacity = 0
        self._closed_workers = 0
        self._cleanup_events: list[WorkerCleanupEvent] = []

    def acquire(self, tenant_id: str) -> TenantSandboxWorker:
        """Get existing tenant worker or create one."""
        normalized_tenant = tenant_id.strip() or "default"
        now = _utc_now()
        now_monotonic = self._clock()
        with self._lock:
            worker = self._workers.get(normalized_tenant)
            if worker is None:
                self._evict_one_for_capacity_unlocked()
                worker = TenantSandboxWorker(
                    tenant_id=normalized_tenant,
                    executor=ThreadPoolExecutor(
                        max_workers=self._max_workers_per_tenant,
                        thread_name_prefix=f"exo-sandbox-{normalized_tenant}",
                    ),
                    created_at_utc=now,
                    last_used_at_utc=now,
                    last_used_monotonic=now_monotonic,
                )
                self._workers[normalized_tenant] = worker
                self._created_workers += 1
            worker.last_used_at_utc = now
            worker.last_used_monotonic = now_monotonic
            worker.execution_count += 1
            return worker

    def evict_tenant(self, tenant_id: str, reason: str = "explicit") -> bool:
        """Evict and shutdown one tenant worker. Returns True when removed."""
        normalized_tenant = tenant_id.strip() or "default"
        with self._lock:
            return self._remove_worker_unlocked(normalized_tenant, reason=reason)

    def stats(self) -> dict[str, int]:
        """Return lightweight pool stats."""
        with self._lock:
            return {
                "tenants": len(self._workers),
                "created_workers": self._created_workers,
                "evicted_workers_total": self._evicted_workers_total,
                "evicted_workers_explicit": self._evicted_workers_explicit,
                "evicted_workers_idle": self._evicted_workers_idle,
                "evicted_workers_capacity": self._evicted_workers_capacity,
                "closed_workers": self._closed_workers,
            }

    def cleanup_events(self, limit: int = 20) -> list[dict[str, str]]:
        """Return recent worker cleanup events for observability/testing."""
        size = max(1, int(limit))
        with self._lock:
            tail = self._cleanup_events[-size:]
            return [
                {
                    "tenant_id": event.tenant_id,
                    "reason": event.reason,
                    "timestamp_utc": event.timestamp_utc,
                }
                for event in tail
            ]

    def evict_idle(self, max_idle_seconds: float) -> list[str]:
        """Evict workers idle longer than max_idle_seconds and return tenant IDs."""
        threshold = max(0.0, float(max_idle_seconds))
        now_monotonic = self._clock()
        with self._lock:
            to_evict = [
                tenant_id
                for tenant_id, worker in self._workers.items()
                if (now_monotonic - worker.last_used_monotonic) > threshold
            ]
        evicted: list[str] = []
        for tenant_id in to_evict:
            if self.evict_tenant(tenant_id, reason="idle_ttl"):
                evicted.append(tenant_id)
        return evicted

    def close(self) -> None:
        """Shutdown all workers and clear the pool."""
        with self._lock:
            tenant_ids = list(self._workers.keys())
            for tenant_id in tenant_ids:
                self._remove_worker_unlocked(tenant_id, reason="close")

    def _evict_one_for_capacity_unlocked(self) -> None:
        if self._max_tenants is None:
            return
        if len(self._workers) < self._max_tenants:
            return
        # Evict least recently used tenant worker.
        lru_tenant = min(self._workers.items(), key=lambda item: item[1].last_used_monotonic)[0]
        self._remove_worker_unlocked(lru_tenant, reason="capacity_lru")

    def _remove_worker_unlocked(self, tenant_id: str, reason: str) -> bool:
        worker = self._workers.pop(tenant_id, None)
        if worker is None:
            return False
        worker.executor.shutdown(wait=False, cancel_futures=True)
        self._evicted_workers_total += 1
        if reason == "explicit":
            self._evicted_workers_explicit += 1
        elif reason == "idle_ttl":
            self._evicted_workers_idle += 1
        elif reason == "capacity_lru":
            self._evicted_workers_capacity += 1
        elif reason == "close":
            self._closed_workers += 1
        self._cleanup_events.append(
            WorkerCleanupEvent(
                tenant_id=tenant_id,
                reason=reason,
                timestamp_utc=_utc_now(),
            )
        )
        if len(self._cleanup_events) > 200:
            self._cleanup_events = self._cleanup_events[-200:]
        return True

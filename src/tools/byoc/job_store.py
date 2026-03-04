"""
File: job_store.py
Path: src/tools/byoc/job_store.py
Role: Durable queue/lease contracts and in-memory implementation for BYOC worker claims.
Used By:
 - src/tools/byoc/connector_runtime.py
Depends On:
 - abc
 - dataclasses
 - threading
Notes:
 - In-memory store is process-local but preserves queued/leased state durably across runtime calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
import threading
import time
import uuid

from src.tools.byoc.job_contracts import ByocToolJobEnvelope


@dataclass(slots=True)
class JobLeaseClaim:
    job: ByocToolJobEnvelope


class ByocJobQueueStore(ABC):
    @abstractmethod
    def enqueue(self, job: ByocToolJobEnvelope) -> None:
        """Persist one queued job."""

    @abstractmethod
    def claim_next(self, *, tenant_id: str, worker_id: str, lease_ttl_seconds: int) -> JobLeaseClaim | None:
        """Claim next available job and attach lease metadata."""

    @abstractmethod
    def complete_claim(self, *, job_id: str, lease_token: str) -> bool:
        """Complete a leased job only when lease token matches active lease."""

    @abstractmethod
    def get_leased_job(self, *, job_id: str, lease_token: str) -> ByocToolJobEnvelope | None:
        """Return active leased job envelope when lease token is valid."""

    @abstractmethod
    def requeue_expired_leases(self) -> int:
        """Requeue expired leased jobs and return count."""

    @abstractmethod
    def cancel_pending_call(self, *, call_id: str) -> int:
        """Cancel queued jobs for a call id; returns affected count."""

    @abstractmethod
    def queue_depth(self) -> int:
        """Return number of queued jobs."""

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        """Return queue/lease lifecycle metrics for one tenant."""
        return {"queued_jobs": self.queue_depth()}

    def cleanup_retention(
        self,
        *,
        tenant_id: str,
        completed_ttl_seconds: int,
        cancelled_ttl_seconds: int,
        max_completed_records: int,
        max_cancelled_records: int,
    ) -> dict[str, int]:
        """Prune completed/cancelled records for one tenant."""
        return {"completed_pruned": 0, "cancelled_pruned": 0}


@dataclass(slots=True)
class _JobState:
    envelope: ByocToolJobEnvelope
    status: str = "queued"  # queued | leased | completed | cancelled
    leased_by_worker_id: str = ""
    lease_token: str = ""
    lease_expires_at_epoch: float = 0.0
    claim_attempt: int = 0
    completed_at_epoch: float = 0.0
    cancelled_at_epoch: float = 0.0
    completed_at_epoch: float = 0.0
    cancelled_at_epoch: float = 0.0


class InMemoryByocJobQueueStore(ByocJobQueueStore):
    """Thread-safe in-memory queue with lease/requeue semantics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, _JobState] = {}
        self._tenant_queue: dict[str, deque[str]] = {}

    def enqueue(self, job: ByocToolJobEnvelope) -> None:
        with self._lock:
            if job.job_id in self._states:
                return
            self._states[job.job_id] = _JobState(envelope=job)
            self._tenant_queue.setdefault(job.tenant_id, deque()).append(job.job_id)

    def claim_next(self, *, tenant_id: str, worker_id: str, lease_ttl_seconds: int) -> JobLeaseClaim | None:
        now = time.time()
        with self._lock:
            self._requeue_expired_leases_unlocked(now)
            queue = self._tenant_queue.setdefault(tenant_id, deque())
            while queue:
                job_id = queue.popleft()
                state = self._states.get(job_id)
                if state is None or state.status != "queued":
                    continue
                state.status = "leased"
                state.leased_by_worker_id = worker_id
                state.lease_token = f"lease_{uuid.uuid4().hex[:12]}"
                state.lease_expires_at_epoch = now + max(int(lease_ttl_seconds), 1)
                state.claim_attempt += 1
                envelope = state.envelope
                envelope.lease_token = state.lease_token
                envelope.lease_expires_at_epoch = int(state.lease_expires_at_epoch)
                envelope.claim_attempt = state.claim_attempt
                return JobLeaseClaim(job=envelope)
            return None

    def complete_claim(self, *, job_id: str, lease_token: str) -> bool:
        with self._lock:
            state = self._states.get(job_id)
            if state is None:
                return False
            if state.status != "leased":
                return False
            now = time.time()
            if state.lease_expires_at_epoch <= now:
                self._requeue_expired_leases_unlocked(now)
                return False
            if state.lease_token != lease_token:
                return False
            state.status = "completed"
            state.completed_at_epoch = now
            return True

    def get_leased_job(self, *, job_id: str, lease_token: str) -> ByocToolJobEnvelope | None:
        with self._lock:
            state = self._states.get(str(job_id))
            if state is None or state.status != "leased":
                return None
            now = time.time()
            if state.lease_expires_at_epoch <= now:
                self._requeue_expired_leases_unlocked(now)
                return None
            if state.lease_token != str(lease_token):
                return None
            return state.envelope

    def requeue_expired_leases(self) -> int:
        with self._lock:
            return self._requeue_expired_leases_unlocked(time.time())

    def cancel_pending_call(self, *, call_id: str) -> int:
        normalized = str(call_id).strip()
        if not normalized:
            return 0
        affected = 0
        with self._lock:
            for state in self._states.values():
                if state.envelope.call_id != normalized:
                    continue
                if state.status == "queued":
                    state.status = "cancelled"
                    state.cancelled_at_epoch = time.time()
                    affected += 1
                elif state.status == "leased":
                    state.lease_expires_at_epoch = 0.0
            self._requeue_expired_leases_unlocked(time.time())
        return affected

    def queue_depth(self) -> int:
        with self._lock:
            return sum(
                1
                for state in self._states.values()
                if state.status == "queued"
            )

    def _requeue_expired_leases_unlocked(self, now: float) -> int:
        requeued = 0
        for job_id, state in self._states.items():
            if state.status == "leased" and state.lease_expires_at_epoch <= now:
                state.status = "queued"
                state.leased_by_worker_id = ""
                state.lease_token = ""
                state.lease_expires_at_epoch = 0.0
                tenant_id = state.envelope.tenant_id
                self._tenant_queue.setdefault(tenant_id, deque()).append(job_id)
                requeued += 1
        return requeued

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        with self._lock:
            queued = 0
            leased = 0
            completed = 0
            cancelled = 0
            for state in self._states.values():
                if state.envelope.tenant_id != normalized:
                    continue
                if state.status == "queued":
                    queued += 1
                elif state.status == "leased":
                    leased += 1
                elif state.status == "completed":
                    completed += 1
                elif state.status == "cancelled":
                    cancelled += 1
            return {
                "queued_jobs": queued,
                "leased_jobs": leased,
                "completed_jobs": completed,
                "cancelled_jobs": cancelled,
            }

    def cleanup_retention(
        self,
        *,
        tenant_id: str,
        completed_ttl_seconds: int,
        cancelled_ttl_seconds: int,
        max_completed_records: int,
        max_cancelled_records: int,
    ) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        if not normalized:
            return {"completed_pruned": 0, "cancelled_pruned": 0}
        now = time.time()
        completed_cutoff = now - max(int(completed_ttl_seconds), 1)
        cancelled_cutoff = now - max(int(cancelled_ttl_seconds), 1)
        completed_pruned = 0
        cancelled_pruned = 0
        with self._lock:
            # TTL pruning first.
            for job_id, state in list(self._states.items()):
                if state.envelope.tenant_id != normalized:
                    continue
                if state.status == "completed" and state.completed_at_epoch > 0 and state.completed_at_epoch <= completed_cutoff:
                    self._states.pop(job_id, None)
                    completed_pruned += 1
                elif (
                    state.status == "cancelled"
                    and state.cancelled_at_epoch > 0
                    and state.cancelled_at_epoch <= cancelled_cutoff
                ):
                    self._states.pop(job_id, None)
                    cancelled_pruned += 1

            # Bounded retention by max record counts.
            completed_rows: list[tuple[str, float]] = []
            cancelled_rows: list[tuple[str, float]] = []
            for job_id, state in self._states.items():
                if state.envelope.tenant_id != normalized:
                    continue
                if state.status == "completed":
                    completed_rows.append((job_id, state.completed_at_epoch))
                elif state.status == "cancelled":
                    cancelled_rows.append((job_id, state.cancelled_at_epoch))
            completed_rows.sort(key=lambda item: item[1])
            cancelled_rows.sort(key=lambda item: item[1])

            overflow_completed = max(0, len(completed_rows) - max(int(max_completed_records), 0))
            overflow_cancelled = max(0, len(cancelled_rows) - max(int(max_cancelled_records), 0))
            for job_id, _ in completed_rows[:overflow_completed]:
                if self._states.pop(job_id, None) is not None:
                    completed_pruned += 1
            for job_id, _ in cancelled_rows[:overflow_cancelled]:
                if self._states.pop(job_id, None) is not None:
                    cancelled_pruned += 1
        return {
            "completed_pruned": completed_pruned,
            "cancelled_pruned": cancelled_pruned,
        }


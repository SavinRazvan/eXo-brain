"""
File: connector_runtime.py
Path: src/tools/byoc/connector_runtime.py
Role: BYOC pull-worker execution adapter that queues jobs and ingests signed worker results.
Used By:
 - src/runtime/tenant_runtime.py
 - src/api/routers/runtime_control.py
Depends On:
 - threading
 - src/tools/execution_adapter.py
Notes:
 - Slice 4.0 skeleton: synchronous execute waits for worker-submitted result envelopes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
import time
from time import perf_counter
from typing import Any
import uuid

from src.schemas.tool_io import (
    ExecutionMetadata,
    NormalizedError,
    ToolAudit,
    ToolCallContext,
    ToolExecutionMode,
    ToolResult,
    ToolStatus,
)
from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolJobEnvelope, ByocToolResultEnvelope
from src.tools.byoc.job_store import ByocJobQueueStore, InMemoryByocJobQueueStore
from src.tools.byoc.result_store import (
    ByocResultIngestOutcome,
    ByocResultStore,
    InMemoryByocResultStore,
    InMemoryReplayGuard,
    ReplayGuard,
)
from src.tools.byoc.worker_auth import mint_worker_token, verify_worker_token
from src.tools.execution_adapter import ToolExecutionAdapter
from src.tools.registry import ToolDescriptor


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalized_nonce(value: str) -> str:
    return str(value).strip()


class TenantByocConnectorRuntime(ToolExecutionAdapter):
    """Tenant-scoped BYOC pull-worker adapter with idempotent result ingestion."""

    def __init__(
        self,
        *,
        worker_jwt_secret: str,
        worker_token_ttl_seconds: int = 300,
        lease_ttl_seconds: int = 30,
        replay_ttl_seconds: int = 300,
        cleanup_interval_seconds: int = 30,
        completed_ttl_seconds: int = 3600,
        cancelled_ttl_seconds: int = 3600,
        result_ttl_seconds: int = 3600,
        idempotency_ttl_seconds: int = 3600,
        max_completed_records: int = 2000,
        max_cancelled_records: int = 2000,
        max_result_records: int = 2000,
        job_store: ByocJobQueueStore | None = None,
        result_store: ByocResultStore | None = None,
        replay_guard: ReplayGuard | None = None,
    ) -> None:
        self._worker_jwt_secret = worker_jwt_secret
        self._worker_token_ttl_seconds = max(int(worker_token_ttl_seconds), 1)
        self._lease_ttl_seconds = max(int(lease_ttl_seconds), 1)
        self._replay_ttl_seconds = max(int(replay_ttl_seconds), 1)
        self._cleanup_interval_seconds = max(int(cleanup_interval_seconds), 1)
        self._completed_ttl_seconds = max(int(completed_ttl_seconds), 1)
        self._cancelled_ttl_seconds = max(int(cancelled_ttl_seconds), 1)
        self._result_ttl_seconds = max(int(result_ttl_seconds), 1)
        self._idempotency_ttl_seconds = max(int(idempotency_ttl_seconds), 1)
        self._max_completed_records = max(int(max_completed_records), 0)
        self._max_cancelled_records = max(int(max_cancelled_records), 0)
        self._max_result_records = max(int(max_result_records), 0)
        self._job_store = job_store or InMemoryByocJobQueueStore()
        self._result_store = result_store or InMemoryByocResultStore()
        self._replay_guard = replay_guard or InMemoryReplayGuard()
        self._lock = threading.Lock()
        self._enqueued_jobs_total = 0
        self._claimed_jobs_total = 0
        self._submitted_results_total = 0
        self._duplicate_results_total = 0
        self._cancel_requested_total = 0
        self._lease_requeue_total = 0
        self._cleanup_runs_total = 0
        self._cleanup_pruned_total = 0
        self._last_cleanup_epoch = 0.0
        self._progress_events_by_call_id: dict[str, list[dict[str, str]]] = {}

    @property
    def backend_id(self) -> str:
        return "byoc_pull_worker_runtime"

    def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
        started = _utc_now()
        started_clock = perf_counter()
        timeout_ms = max(int(descriptor.timeout_ms), 1)
        tenant_id = str(call.tenant_id or "default").strip() or "default"
        self._run_periodic_cleanup(tenant_id=tenant_id)
        idempotency_key = f"{tenant_id}:{call.call_id}:{call.run_id or 'run'}"
        job = ByocToolJobEnvelope(
            job_id=f"job_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            run_id=str(call.run_id),
            call_id=str(call.call_id),
            tool_name=descriptor.name,
            arguments=dict(call.arguments),
            timeout_ms=timeout_ms,
            correlation_id=str(call.call_id),
            idempotency_key=idempotency_key,
        )
        self._job_store.enqueue(job)
        self._record_progress(
            call_id=call.call_id,
            tool_name=descriptor.name,
            state="queued",
            job_id=job.job_id,
        )
        with self._lock:
            self._enqueued_jobs_total += 1

        deadline = perf_counter() + (timeout_ms / 1000.0)
        while True:
            self._requeue_expired_leases()
            result = self._result_store.consume(job.job_id)
            if result is not None:
                break
            remaining = deadline - perf_counter()
            if remaining <= 0:
                timeout_result = self._timeout_result(call, started, started_clock, timeout_ms, tenant_id, job.job_id)
                self._record_progress(
                    call_id=call.call_id,
                    tool_name=descriptor.name,
                    state="timed_out",
                    tool_status=timeout_result.status.value,
                    error_code=str(timeout_result.error.code or ""),
                    job_id=job.job_id,
                )
                return timeout_result
            threading.Event().wait(timeout=min(remaining, 0.1))
        mapped = self._map_result(call, started, started_clock, timeout_ms, tenant_id, result)
        self._record_progress(
            call_id=call.call_id,
            tool_name=descriptor.name,
            state=self._terminal_state(mapped.status),
            tool_status=mapped.status.value,
            error_code=str(mapped.error.code or ""),
            job_id=result.job_id,
            lease_token=str(result.lease_token),
        )
        return mapped

    def issue_worker_token(self, *, tenant_id: str, worker_id: str, ttl_seconds: int | None = None) -> str:
        return mint_worker_token(
            tenant_id=tenant_id,
            worker_id=worker_id,
            secret=self._worker_jwt_secret,
            ttl_seconds=self._worker_token_ttl_seconds if ttl_seconds is None else ttl_seconds,
        )

    def claim_next_job(self, *, tenant_id: str, worker_token: str, request_nonce: str) -> dict[str, Any] | None:
        self._run_periodic_cleanup(tenant_id=tenant_id)
        claims = verify_worker_token(
            token=worker_token,
            secret=self._worker_jwt_secret,
            expected_tenant_id=tenant_id,
        )
        nonce = _normalized_nonce(request_nonce)
        if not nonce:
            raise ValueError("WORKER_NONCE_REQUIRED")
        replay_key = f"{tenant_id}:claim:{claims.token_id}:{nonce}"
        if not self._replay_guard.mark_once(key=replay_key, ttl_seconds=self._replay_ttl_seconds):
            raise ValueError("WORKER_REQUEST_REPLAYED")
        claim = self._job_store.claim_next(
            tenant_id=tenant_id,
            worker_id=claims.worker_id,
            lease_ttl_seconds=self._lease_ttl_seconds,
        )
        if claim is None:
            return None
        with self._lock:
            self._claimed_jobs_total += 1
        self._record_progress(
            call_id=claim.job.call_id,
            tool_name=claim.job.tool_name,
            state="running",
            job_id=claim.job.job_id,
            lease_token=claim.job.lease_token,
            lease_expires_at_epoch=str(claim.job.lease_expires_at_epoch),
            claim_attempt=str(claim.job.claim_attempt),
        )
        job = claim.job
        return {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "run_id": job.run_id,
            "call_id": job.call_id,
            "tool_name": job.tool_name,
            "arguments": dict(job.arguments),
            "timeout_ms": job.timeout_ms,
            "correlation_id": job.correlation_id,
            "idempotency_key": job.idempotency_key,
            "lease_token": job.lease_token,
            "lease_expires_at_epoch": job.lease_expires_at_epoch,
            "claim_attempt": job.claim_attempt,
        }

    def submit_result(
        self,
        *,
        tenant_id: str,
        worker_token: str,
        request_nonce: str,
        result: ByocToolResultEnvelope,
    ) -> ByocResultIngestOutcome:
        self._run_periodic_cleanup(tenant_id=tenant_id)
        claims = verify_worker_token(
            token=worker_token,
            secret=self._worker_jwt_secret,
            expected_tenant_id=tenant_id,
        )
        nonce = _normalized_nonce(request_nonce)
        if not nonce:
            raise ValueError("WORKER_NONCE_REQUIRED")
        replay_key = f"{tenant_id}:submit:{claims.token_id}:{nonce}"
        if not self._replay_guard.mark_once(key=replay_key, ttl_seconds=self._replay_ttl_seconds):
            raise ValueError("WORKER_REQUEST_REPLAYED")
        if result.tenant_id != tenant_id:
            raise ValueError("WORKER_RESULT_TENANT_MISMATCH")
        outcome = self._result_store.ingest(result)
        if outcome.duplicate:
            with self._lock:
                self._duplicate_results_total += 1
            return outcome
        lease_ok = self._job_store.complete_claim(job_id=result.job_id, lease_token=result.lease_token)
        if not lease_ok:
            return ByocResultIngestOutcome(
                accepted=False,
                duplicate=False,
                reason_code="BYOC_LEASE_INVALID_OR_EXPIRED",
            )
        if outcome.accepted:
            with self._lock:
                self._submitted_results_total += 1
        return outcome

    def request_cancellation(self, call_id: str) -> bool:
        normalized = str(call_id).strip()
        if not normalized:
            return False
        affected = self._job_store.cancel_pending_call(call_id=normalized)
        with self._lock:
            self._cancel_requested_total += 1
        return affected > 0

    def control_stats(self) -> dict[str, int]:
        with self._lock:
            metrics = {
                "enqueued_jobs_total": self._enqueued_jobs_total,
                "claimed_jobs_total": self._claimed_jobs_total,
                "submitted_results_total": self._submitted_results_total,
                "duplicate_results_total": self._duplicate_results_total,
                "cancel_requested_total": self._cancel_requested_total,
                "lease_requeue_total": self._lease_requeue_total,
                "cleanup_runs_total": self._cleanup_runs_total,
                "cleanup_pruned_total": self._cleanup_pruned_total,
                "queue_depth": self._job_store.queue_depth(),
            }
        return metrics

    def control_stats_for_tenant(self, *, tenant_id: str) -> dict[str, int]:
        base = self.control_stats()
        queue_metrics = self._job_store.health_metrics(tenant_id=tenant_id)
        result_metrics = self._result_store.health_metrics(tenant_id=tenant_id)
        replay_metrics = self._replay_guard.health_metrics(tenant_id=tenant_id)
        combined = dict(base)
        combined.update(queue_metrics)
        combined.update(result_metrics)
        combined.update(replay_metrics)
        return combined

    def cleanup_retention(self, *, tenant_id: str, force: bool = False) -> dict[str, int]:
        return self._run_cleanup(tenant_id=tenant_id, force=force)

    def drain_progress_events(self, call_id: str) -> list[dict[str, str]]:
        normalized = str(call_id).strip()
        if not normalized:
            return []
        with self._lock:
            return list(self._progress_events_by_call_id.pop(normalized, []))

    def _requeue_expired_leases(self) -> None:
        requeued = self._job_store.requeue_expired_leases()
        if requeued > 0:
            with self._lock:
                self._lease_requeue_total += requeued

    def _run_periodic_cleanup(self, *, tenant_id: str) -> None:
        self._run_cleanup(tenant_id=tenant_id, force=False)

    def _run_cleanup(self, *, tenant_id: str, force: bool) -> dict[str, int]:
        now = time.time()
        with self._lock:
            should_run = force or ((now - self._last_cleanup_epoch) >= self._cleanup_interval_seconds)
            if not should_run:
                return {"job_records_pruned": 0, "result_records_pruned": 0, "replay_records_pruned": 0}
            self._last_cleanup_epoch = now
        job_pruned = self._job_store.cleanup_retention(
            tenant_id=tenant_id,
            completed_ttl_seconds=self._completed_ttl_seconds,
            cancelled_ttl_seconds=self._cancelled_ttl_seconds,
            max_completed_records=self._max_completed_records,
            max_cancelled_records=self._max_cancelled_records,
        )
        result_pruned = self._result_store.cleanup_retention(
            tenant_id=tenant_id,
            result_ttl_seconds=self._result_ttl_seconds,
            idempotency_ttl_seconds=self._idempotency_ttl_seconds,
            max_result_records=self._max_result_records,
        )
        replay_pruned = self._replay_guard.cleanup_retention(tenant_id=tenant_id)
        job_total = int(job_pruned.get("completed_pruned", 0)) + int(job_pruned.get("cancelled_pruned", 0))
        result_total = int(result_pruned.get("result_payloads_pruned", 0)) + int(result_pruned.get("idempotency_pruned", 0))
        replay_total = int(replay_pruned.get("replay_keys_pruned", 0))
        with self._lock:
            self._cleanup_runs_total += 1
            self._cleanup_pruned_total += job_total + result_total + replay_total
        return {
            "job_records_pruned": job_total,
            "result_records_pruned": result_total,
            "replay_records_pruned": replay_total,
        }

    def _record_progress(
        self,
        *,
        call_id: str,
        tool_name: str,
        state: str,
        tool_status: str = "",
        error_code: str = "",
        job_id: str = "",
        lease_token: str = "",
        lease_expires_at_epoch: str = "",
        claim_attempt: str = "",
    ) -> None:
        normalized = str(call_id).strip()
        if not normalized:
            return
        event = {
            "call_id": normalized,
            "tool_name": str(tool_name),
            "state": str(state),
            "tool_status": str(tool_status),
            "error_code": str(error_code),
            "job_id": str(job_id),
            "lease_token": str(lease_token),
            "lease_expires_at_epoch": str(lease_expires_at_epoch),
            "claim_attempt": str(claim_attempt),
        }
        with self._lock:
            self._progress_events_by_call_id.setdefault(normalized, []).append(event)

    def _terminal_state(self, status: ToolStatus) -> str:
        if status == ToolStatus.SUCCESS:
            return "completed"
        if status == ToolStatus.TIMEOUT:
            return "timed_out"
        if status == ToolStatus.CANCELLED:
            return "cancelled"
        return "failed"

    def _timeout_result(
        self,
        call: ToolCallContext,
        started: str,
        started_clock: float,
        timeout_ms: int,
        tenant_id: str,
        job_id: str,
    ) -> ToolResult:
        return ToolResult(
            schema_version="1.0",
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.TIMEOUT,
            error=NormalizedError(
                code="BYOC_RUNTIME_TIMEOUT",
                category="tool_runtime",
                message=f"BYOC worker result not received before timeout ({timeout_ms}ms).",
                retryable=True,
                details={"backend_id": self.backend_id, "tenant_id": tenant_id, "job_id": job_id},
            ),
            execution=ExecutionMetadata(
                mode_used=ToolExecutionMode.DETERMINISTIC,
                started_at_utc=started,
                finished_at_utc=_utc_now(),
                duration_ms=int((perf_counter() - started_clock) * 1000),
                timeout_ms=timeout_ms,
            ),
            audit=ToolAudit(correlation_id=call.call_id),
        )

    def _map_result(
        self,
        call: ToolCallContext,
        started: str,
        started_clock: float,
        timeout_ms: int,
        tenant_id: str,
        result: ByocToolResultEnvelope,
    ) -> ToolResult:
        status_map = {
            ByocResultStatus.SUCCESS: ToolStatus.SUCCESS,
            ByocResultStatus.ERROR: ToolStatus.ERROR,
            ByocResultStatus.TIMEOUT: ToolStatus.TIMEOUT,
            ByocResultStatus.CANCELLED: ToolStatus.CANCELLED,
        }
        status = status_map.get(result.status, ToolStatus.ERROR)
        payload = {
            "value": result.output or {},
            "runtime": {
                "backend_id": self.backend_id,
                "job_id": result.job_id,
                "idempotency_key": result.idempotency_key,
                "tenant_id": tenant_id,
            },
        }
        err = NormalizedError(
            code=result.error_code or "",
            category="tool_runtime",
            message=result.error_message or "",
            retryable=bool(result.retryable),
            details={
                "backend_id": self.backend_id,
                "tenant_id": tenant_id,
                "job_id": result.job_id,
                "idempotency_key": result.idempotency_key,
            },
        )
        return ToolResult(
            schema_version="1.0",
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=status,
            result=payload if status == ToolStatus.SUCCESS else None,
            error=NormalizedError() if status == ToolStatus.SUCCESS else err,
            execution=ExecutionMetadata(
                mode_used=ToolExecutionMode.DETERMINISTIC,
                started_at_utc=started,
                finished_at_utc=_utc_now(),
                duration_ms=int((perf_counter() - started_clock) * 1000),
                timeout_ms=timeout_ms,
            ),
            audit=ToolAudit(correlation_id=call.call_id),
        )


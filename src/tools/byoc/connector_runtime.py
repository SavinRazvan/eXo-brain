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
from src.tools.byoc.integrity_verifier import verify_result_artifact_metadata
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

from src.tools.artifact_store import (
    ARTIFACT_BUNDLE_HASH_METADATA_KEY,
    ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY,
    ARTIFACT_SIGNATURE_VERSION_METADATA_KEY,
)


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
        max_claim_attempts_before_dlq: int = 3,
        cost_limit_microunits_per_tenant: int = 1_000_000,
        enforce_cost_limit: bool = False,
        cost_success_microunits: int = 100,
        cost_error_microunits: int = 40,
        cost_timeout_microunits: int = 60,
        cost_cancelled_microunits: int = 20,
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
        self._max_claim_attempts_before_dlq = max(int(max_claim_attempts_before_dlq), 1)
        self._cost_limit_microunits_per_tenant = max(int(cost_limit_microunits_per_tenant), 0)
        self._enforce_cost_limit = bool(enforce_cost_limit)
        self._cost_success_microunits = max(int(cost_success_microunits), 0)
        self._cost_error_microunits = max(int(cost_error_microunits), 0)
        self._cost_timeout_microunits = max(int(cost_timeout_microunits), 0)
        self._cost_cancelled_microunits = max(int(cost_cancelled_microunits), 0)
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
        self._dlq_moved_total = 0
        self._dlq_replayed_total = 0
        self._cleanup_runs_total = 0
        self._cleanup_pruned_total = 0
        self._last_cleanup_epoch = 0.0
        self._progress_events_by_call_id: dict[str, list[dict[str, str]]] = {}
        self._tenant_cost_microunits_total: dict[str, int] = {}
        self._tenant_submit_attempts_total: dict[str, int] = {}
        self._tenant_rejected_results_total: dict[str, int] = {}
        self._tenant_rejections_by_reason: dict[str, dict[str, int]] = {}

    @property
    def backend_id(self) -> str:
        return "byoc_pull_worker_runtime"

    def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
        started = _utc_now()
        started_clock = perf_counter()
        timeout_ms = max(int(descriptor.timeout_ms), 1)
        tenant_id = str(call.tenant_id or "default").strip() or "default"
        if self._enforce_cost_limit and self._cost_limit_exceeded(tenant_id=tenant_id):
            return self._cost_limit_result(call, timeout_ms=timeout_ms, tenant_id=tenant_id)
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
            tool_version=str(descriptor.metadata.get("tool_version", "")),
            package_ref=str(descriptor.metadata.get("package_ref", "")),
            entry_file=str(descriptor.metadata.get("entry_file", "")),
            entrypoint=str(descriptor.metadata.get("entrypoint", "")),
            artifact_bundle_hash_sha256=str(descriptor.metadata.get(ARTIFACT_BUNDLE_HASH_METADATA_KEY, "")),
            artifact_bundle_signature_hmac_sha256=str(
                descriptor.metadata.get(ARTIFACT_BUNDLE_SIGNATURE_METADATA_KEY, "")
            ),
            artifact_signature_version=str(descriptor.metadata.get(ARTIFACT_SIGNATURE_VERSION_METADATA_KEY, "")),
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
            self._requeue_expired_leases(tenant_id=tenant_id)
            result = self._result_store.consume(job.job_id)
            if result is not None:
                break
            remaining = deadline - perf_counter()
            if remaining <= 0:
                timeout_result = self._timeout_result(call, started, started_clock, timeout_ms, tenant_id, job.job_id)
                self._record_tenant_cost(tenant_id=tenant_id, amount=self._cost_timeout_microunits)
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
        self._requeue_expired_leases(tenant_id=tenant_id)
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
            "tool_version": job.tool_version,
            "package_ref": job.package_ref,
            "entry_file": job.entry_file,
            "entrypoint": job.entrypoint,
            "artifact_bundle_hash_sha256": job.artifact_bundle_hash_sha256,
            "artifact_bundle_signature_hmac_sha256": job.artifact_bundle_signature_hmac_sha256,
            "artifact_signature_version": job.artifact_signature_version,
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
        return self._ingest_result_after_auth(tenant_id=tenant_id, result=result)

    def submit_result_webhook(
        self,
        *,
        tenant_id: str,
        webhook_secret: str,
        webhook_request_id: str,
        result: ByocToolResultEnvelope,
    ) -> ByocResultIngestOutcome:
        self._run_periodic_cleanup(tenant_id=tenant_id)
        provided_secret = str(webhook_secret).strip()
        if not provided_secret or provided_secret != self._worker_jwt_secret:
            raise ValueError("WEBHOOK_AUTH_INVALID")
        request_id = _normalized_nonce(webhook_request_id)
        if not request_id:
            raise ValueError("WEBHOOK_REQUEST_ID_REQUIRED")
        replay_key = f"{tenant_id}:webhook:{request_id}"
        if not self._replay_guard.mark_once(key=replay_key, ttl_seconds=self._replay_ttl_seconds):
            raise ValueError("WEBHOOK_REQUEST_REPLAYED")
        return self._ingest_result_after_auth(tenant_id=tenant_id, result=result)

    def _ingest_result_after_auth(
        self,
        *,
        tenant_id: str,
        result: ByocToolResultEnvelope,
    ) -> ByocResultIngestOutcome:
        self._increment_tenant_submit_attempt(tenant_id=tenant_id)
        if result.tenant_id != tenant_id:
            self._increment_tenant_rejection(tenant_id=tenant_id, reason_code="WORKER_RESULT_TENANT_MISMATCH")
            raise ValueError("WORKER_RESULT_TENANT_MISMATCH")
        existing_key = str(result.idempotency_key).strip()
        if existing_key and self._result_store.has_idempotency_key(existing_key):
            with self._lock:
                self._duplicate_results_total += 1
            return ByocResultIngestOutcome(
                accepted=True,
                duplicate=True,
                reason_code="IDEMPOTENT_DUPLICATE",
            )
        leased_job = self._job_store.get_leased_job(job_id=result.job_id, lease_token=result.lease_token)
        if leased_job is None:
            self._increment_tenant_rejection(tenant_id=tenant_id, reason_code="BYOC_LEASE_INVALID_OR_EXPIRED")
            return ByocResultIngestOutcome(
                accepted=False,
                duplicate=False,
                reason_code="BYOC_LEASE_INVALID_OR_EXPIRED",
            )
        artifact_reason = verify_result_artifact_metadata(
            expected_job=leased_job,
            submitted_result=result,
        )
        if artifact_reason:
            self._increment_tenant_rejection(tenant_id=tenant_id, reason_code=artifact_reason)
            return ByocResultIngestOutcome(
                accepted=False,
                duplicate=False,
                reason_code=artifact_reason,
            )
        lease_ok = self._job_store.complete_claim(job_id=result.job_id, lease_token=result.lease_token)
        if not lease_ok:
            self._increment_tenant_rejection(tenant_id=tenant_id, reason_code="BYOC_LEASE_INVALID_OR_EXPIRED")
            return ByocResultIngestOutcome(
                accepted=False,
                duplicate=False,
                reason_code="BYOC_LEASE_INVALID_OR_EXPIRED",
            )
        outcome = self._result_store.ingest(result)
        if outcome.duplicate:
            with self._lock:
                self._duplicate_results_total += 1
            return outcome
        if outcome.accepted:
            with self._lock:
                self._submitted_results_total += 1
        elif not outcome.duplicate:
            self._increment_tenant_rejection(tenant_id=tenant_id, reason_code=outcome.reason_code)
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
                "dlq_moved_total": self._dlq_moved_total,
                "dlq_replayed_total": self._dlq_replayed_total,
                "cleanup_runs_total": self._cleanup_runs_total,
                "cleanup_pruned_total": self._cleanup_pruned_total,
                "queue_depth": self._job_store.queue_depth(),
                "cost_limit_microunits_per_tenant": self._cost_limit_microunits_per_tenant,
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
        with self._lock:
            tenant_cost = int(self._tenant_cost_microunits_total.get(tenant_id, 0))
            tenant_submit_attempts = int(self._tenant_submit_attempts_total.get(tenant_id, 0))
            tenant_rejected_total = int(self._tenant_rejected_results_total.get(tenant_id, 0))
            reason_counts = dict(self._tenant_rejections_by_reason.get(tenant_id, {}))
        combined["tenant_cost_microunits_total"] = tenant_cost
        combined["tenant_cost_limit_microunits"] = int(self._cost_limit_microunits_per_tenant)
        combined["tenant_cost_remaining_microunits"] = max(
            int(self._cost_limit_microunits_per_tenant) - tenant_cost,
            0,
        )
        combined["tenant_submit_attempts_total"] = tenant_submit_attempts
        combined["tenant_rejected_results_total"] = tenant_rejected_total
        for reason, count in reason_counts.items():
            combined[f"tenant_rejected_reason_{reason}"] = int(count)
        return combined

    def cleanup_retention(self, *, tenant_id: str, force: bool = False) -> dict[str, int]:
        return self._run_cleanup(tenant_id=tenant_id, force=force)

    def list_dead_letter_jobs(self, *, tenant_id: str, limit: int = 100) -> list[dict[str, str]]:
        return self._job_store.list_dead_letter_jobs(tenant_id=tenant_id, limit=limit)

    def replay_dead_letter_job(self, *, tenant_id: str, job_id: str) -> bool:
        replayed = self._job_store.replay_dead_letter_job(tenant_id=tenant_id, job_id=job_id)
        if replayed:
            with self._lock:
                self._dlq_replayed_total += 1
        return replayed

    def drain_progress_events(self, call_id: str) -> list[dict[str, str]]:
        normalized = str(call_id).strip()
        if not normalized:
            return []
        with self._lock:
            return list(self._progress_events_by_call_id.pop(normalized, []))

    def _requeue_expired_leases(self, *, tenant_id: str | None = None) -> None:
        normalized_tenant = str(tenant_id or "").strip()
        before_dlq = self._job_store.dead_letter_count(tenant_id=normalized_tenant) if normalized_tenant else 0
        requeued = self._job_store.requeue_expired_leases(
            max_claim_attempts_before_dlq=self._max_claim_attempts_before_dlq
        )
        if requeued > 0:
            with self._lock:
                self._lease_requeue_total += requeued
        after_dlq = self._job_store.dead_letter_count(tenant_id=normalized_tenant) if normalized_tenant else 0
        if after_dlq > before_dlq:
            with self._lock:
                self._dlq_moved_total += max(after_dlq - before_dlq, 0)

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

    def _cost_for_status(self, status: ToolStatus) -> int:
        if status == ToolStatus.SUCCESS:
            return self._cost_success_microunits
        if status == ToolStatus.TIMEOUT:
            return self._cost_timeout_microunits
        if status == ToolStatus.CANCELLED:
            return self._cost_cancelled_microunits
        return self._cost_error_microunits

    def _record_tenant_cost(self, *, tenant_id: str, amount: int) -> None:
        normalized = str(tenant_id).strip() or "default"
        with self._lock:
            self._tenant_cost_microunits_total[normalized] = int(
                self._tenant_cost_microunits_total.get(normalized, 0)
            ) + max(int(amount), 0)

    def _increment_tenant_submit_attempt(self, *, tenant_id: str) -> None:
        normalized = str(tenant_id).strip() or "default"
        with self._lock:
            self._tenant_submit_attempts_total[normalized] = int(self._tenant_submit_attempts_total.get(normalized, 0)) + 1

    def _increment_tenant_rejection(self, *, tenant_id: str, reason_code: str) -> None:
        normalized = str(tenant_id).strip() or "default"
        reason = str(reason_code or "UNKNOWN").strip() or "UNKNOWN"
        with self._lock:
            self._tenant_rejected_results_total[normalized] = int(self._tenant_rejected_results_total.get(normalized, 0)) + 1
            bucket = self._tenant_rejections_by_reason.setdefault(normalized, {})
            bucket[reason] = int(bucket.get(reason, 0)) + 1

    def _cost_limit_exceeded(self, *, tenant_id: str) -> bool:
        if self._cost_limit_microunits_per_tenant <= 0:
            return False
        normalized = str(tenant_id).strip() or "default"
        with self._lock:
            consumed = int(self._tenant_cost_microunits_total.get(normalized, 0))
        return consumed >= int(self._cost_limit_microunits_per_tenant)

    def _cost_limit_result(self, call: ToolCallContext, *, timeout_ms: int, tenant_id: str) -> ToolResult:
        self._increment_tenant_rejection(tenant_id=tenant_id, reason_code="BYOC_COST_LIMIT_EXCEEDED")
        return ToolResult(
            schema_version="1.0",
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.ERROR,
            error=NormalizedError(
                code="BYOC_COST_LIMIT_EXCEEDED",
                category="policy",
                message="BYOC tenant cost limit exceeded.",
                retryable=False,
                details={"backend_id": self.backend_id, "tenant_id": tenant_id},
            ),
            execution=ExecutionMetadata(
                mode_used=ToolExecutionMode.DETERMINISTIC,
                timeout_ms=timeout_ms,
            ),
            audit=ToolAudit(correlation_id=call.call_id),
        )

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
        self._record_tenant_cost(tenant_id=tenant_id, amount=self._cost_for_status(status))
        payload = {
            "value": result.output or {},
            "runtime": {
                "backend_id": self.backend_id,
                "job_id": result.job_id,
                "idempotency_key": result.idempotency_key,
                "tenant_id": tenant_id,
                "tool_version": result.tool_version,
                "artifact_bundle_hash_sha256": result.artifact_bundle_hash_sha256,
                "artifact_bundle_signature_hmac_sha256": result.artifact_bundle_signature_hmac_sha256,
                "artifact_signature_version": result.artifact_signature_version,
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
                "tool_version": result.tool_version,
                "artifact_bundle_hash_sha256": result.artifact_bundle_hash_sha256,
                "artifact_bundle_signature_hmac_sha256": result.artifact_bundle_signature_hmac_sha256,
                "artifact_signature_version": result.artifact_signature_version,
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


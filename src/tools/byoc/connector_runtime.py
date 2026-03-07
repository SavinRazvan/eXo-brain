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
from src.policies.byoc_fairness import ByocFairAdmissionCoordinator, FairAdmissionToken
from src.tools.byoc.job_contracts import ByocResultStatus, ByocToolJobEnvelope, ByocToolResultEnvelope
from src.tools.byoc.integrity_verifier import verify_result_artifact_metadata
from src.tools.byoc.job_store import ByocJobQueueStore, InMemoryByocJobQueueStore
from src.tools.byoc.result_store import (
    ByocConflictCountRecord,
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


def _metric_token(value: str) -> str:
    token = str(value or "").strip().lower()
    if not token:
        return "unknown"
    sanitized = []
    for char in token:
        if char.isalnum():
            sanitized.append(char)
        else:
            sanitized.append("_")
    return "".join(sanitized).strip("_") or "unknown"


class TenantByocConnectorRuntime(ToolExecutionAdapter):
    """Tenant-scoped BYOC pull-worker adapter with idempotent result ingestion."""
    _coordinator_lock = threading.Lock()
    _fair_admission_by_key: dict[int, ByocFairAdmissionCoordinator] = {}

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
        enable_cost_window_policy: bool = False,
        cost_window_seconds: int = 3600,
        cost_success_microunits: int = 100,
        cost_error_microunits: int = 40,
        cost_timeout_microunits: int = 60,
        cost_cancelled_microunits: int = 20,
        budget_partition_scope: str = "tenant",
        budget_partition_limits_microunits: dict[str, int] | None = None,
        fair_admission_enabled: bool = False,
        fair_admission_max_inflight_global: int = 8,
        fair_admission_wait_timeout_ms: int = 1000,
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
        self._enable_cost_window_policy = bool(enable_cost_window_policy)
        self._cost_window_seconds = max(int(cost_window_seconds), 1)
        self._cost_success_microunits = max(int(cost_success_microunits), 0)
        self._cost_error_microunits = max(int(cost_error_microunits), 0)
        self._cost_timeout_microunits = max(int(cost_timeout_microunits), 0)
        self._cost_cancelled_microunits = max(int(cost_cancelled_microunits), 0)
        self._budget_partition_scope = self._normalize_budget_partition_scope(budget_partition_scope)
        self._budget_partition_limits_microunits = self._normalize_budget_partition_limits(
            budget_partition_limits_microunits or {}
        )
        self._fair_admission_enabled = bool(fair_admission_enabled)
        self._fair_admission_max_inflight_global = max(int(fair_admission_max_inflight_global), 1)
        self._fair_admission_wait_timeout_ms = max(int(fair_admission_wait_timeout_ms), 1)
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
        self._dlq_replay_failed_total = 0
        self._cleanup_runs_total = 0
        self._cleanup_pruned_total = 0
        self._last_cleanup_epoch = 0.0
        self._progress_events_by_call_id: dict[str, list[dict[str, str]]] = {}
        self._tenant_cost_microunits_total: dict[str, int] = {}
        self._tenant_cost_window_started_epoch: dict[str, int] = {}
        self._tenant_cost_window_microunits: dict[str, int] = {}
        self._tenant_partition_cost_microunits_total: dict[str, dict[str, int]] = {}
        self._tenant_partition_cost_window_started_epoch: dict[str, dict[str, int]] = {}
        self._tenant_partition_cost_window_microunits: dict[str, dict[str, int]] = {}
        self._tenant_submit_attempts_total: dict[str, int] = {}
        self._tenant_rejected_results_total: dict[str, int] = {}
        self._tenant_rejections_by_reason: dict[str, dict[str, int]] = {}
        self._fair_admission_timeout_total = 0
        self._tenant_fair_admission_timeout_total: dict[str, int] = {}

    @property
    def backend_id(self) -> str:
        return "byoc_pull_worker_runtime"

    def execute(self, call: ToolCallContext, descriptor: ToolDescriptor) -> ToolResult:
        started = _utc_now()
        started_clock = perf_counter()
        timeout_ms = max(int(descriptor.timeout_ms), 1)
        tenant_id = str(call.tenant_id or "default").strip() or "default"
        if self._enforce_cost_limit:
            exceeded, reason_code, rejection_details = self._cost_limit_exceeded(
                tenant_id=tenant_id,
                provider_id=call.provider_id,
                tool_name=descriptor.name,
            )
            if exceeded:
                return self._cost_limit_result(
                    call,
                    timeout_ms=timeout_ms,
                    tenant_id=tenant_id,
                    reason_code=reason_code,
                    details=rejection_details,
                )
        fair_token: FairAdmissionToken | None = None
        if self._fair_admission_enabled:
            fair_token = self._acquire_fair_admission(tenant_id=tenant_id)
            if fair_token is None:
                return self._fair_admission_timeout_result(call, timeout_ms=timeout_ms, tenant_id=tenant_id)
        self._run_periodic_cleanup(tenant_id=tenant_id)
        try:
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
                    self._record_tenant_cost(
                        tenant_id=tenant_id,
                        provider_id=call.provider_id,
                        tool_name=descriptor.name,
                        amount=self._cost_timeout_microunits,
                    )
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
        finally:
            if fair_token is not None:
                self._fair_admission_coordinator().release(fair_token)

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
                "dlq_replay_failed_total": self._dlq_replay_failed_total,
                "cleanup_runs_total": self._cleanup_runs_total,
                "cleanup_pruned_total": self._cleanup_pruned_total,
                "queue_depth": self._job_store.queue_depth(),
                "cost_limit_microunits_per_tenant": self._cost_limit_microunits_per_tenant,
                "cost_window_policy_enabled": int(self._enable_cost_window_policy),
                "cost_window_seconds": self._cost_window_seconds,
                "budget_partition_scope_per_provider_enabled": int(self._budget_partition_scope == "per_provider"),
                "budget_partition_scope_per_tool_enabled": int(self._budget_partition_scope == "per_tool"),
                "budget_partition_limits_configured_total": len(self._budget_partition_limits_microunits),
                "fair_admission_enabled": int(self._fair_admission_enabled),
                "fair_admission_wait_timeout_ms": self._fair_admission_wait_timeout_ms,
                "fair_admission_timeout_total": self._fair_admission_timeout_total,
            }
        if self._fair_admission_enabled:
            metrics.update(self._fair_admission_coordinator().stats())
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
        window_start, window_cost = self._window_state(tenant_id=tenant_id, now=time.time())
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
        combined["tenant_cost_window_policy_enabled"] = int(self._enable_cost_window_policy)
        combined["tenant_cost_window_seconds"] = int(self._cost_window_seconds)
        combined["tenant_cost_window_started_epoch"] = int(window_start)
        combined["tenant_cost_window_microunits"] = int(window_cost)
        combined["tenant_cost_window_remaining_microunits"] = max(
            int(self._cost_limit_microunits_per_tenant) - int(window_cost),
            0,
        )
        with self._lock:
            partition_totals = dict(self._tenant_partition_cost_microunits_total.get(tenant_id, {}))
            partition_windows = dict(self._tenant_partition_cost_window_microunits.get(tenant_id, {}))
        combined["tenant_budget_partitions_tracked_total"] = len(partition_totals)
        for partition_key, partition_total in partition_totals.items():
            metric_key = _metric_token(partition_key)
            combined[f"tenant_cost_partition_{metric_key}_microunits_total"] = int(partition_total)
            partition_limit = int(self._partition_limit_for_key(partition_key))
            combined[f"tenant_cost_partition_{metric_key}_limit_microunits"] = partition_limit
            combined[f"tenant_cost_partition_{metric_key}_remaining_microunits"] = max(partition_limit - int(partition_total), 0)
            if self._enable_cost_window_policy:
                window_total = int(partition_windows.get(partition_key, 0))
                combined[f"tenant_cost_partition_{metric_key}_window_microunits"] = window_total
                combined[f"tenant_cost_partition_{metric_key}_window_remaining_microunits"] = max(
                    partition_limit - window_total,
                    0,
                )
        combined["tenant_submit_attempts_total"] = tenant_submit_attempts
        combined["tenant_rejected_results_total"] = tenant_rejected_total
        combined["tenant_fair_admission_timeout_total"] = int(
            self._tenant_fair_admission_timeout_total.get(tenant_id, 0)
        )
        conflict_counts = self._result_store.list_conflict_counts(tenant_id=tenant_id)
        combined["tenant_conflict_total"] = sum(int(item.count) for item in conflict_counts)
        for item in conflict_counts:
            reason_key = _metric_token(item.reason_code)
            strategy_key = _metric_token(item.strategy)
            tool_key = _metric_token(item.tool_name)
            version_key = _metric_token(item.tool_version)
            combined[f"tenant_conflict_reason_{reason_key}"] = combined.get(
                f"tenant_conflict_reason_{reason_key}",
                0,
            ) + int(item.count)
            combined[f"tenant_conflict_strategy_{strategy_key}"] = combined.get(
                f"tenant_conflict_strategy_{strategy_key}",
                0,
            ) + int(item.count)
            combined[f"tenant_conflict_tool_{tool_key}_version_{version_key}_reason_{reason_key}"] = int(item.count)
        for reason, count in reason_counts.items():
            combined[f"tenant_rejected_reason_{reason}"] = int(count)
        return combined

    def conflict_counts_for_tenant(self, *, tenant_id: str) -> list[ByocConflictCountRecord]:
        return self._result_store.list_conflict_counts(tenant_id=tenant_id)

    def cleanup_retention(self, *, tenant_id: str, force: bool = False) -> dict[str, int]:
        return self._run_cleanup(tenant_id=tenant_id, force=force)

    def list_dead_letter_jobs(self, *, tenant_id: str, limit: int = 100) -> list[dict[str, str]]:
        return self._job_store.list_dead_letter_jobs(tenant_id=tenant_id, limit=limit)

    def replay_dead_letter_job(self, *, tenant_id: str, job_id: str) -> bool:
        replayed = self._job_store.replay_dead_letter_job(tenant_id=tenant_id, job_id=job_id)
        with self._lock:
            if replayed:
                self._dlq_replayed_total += 1
            else:
                self._dlq_replay_failed_total += 1
        return replayed

    def replay_dead_letter_jobs(
        self,
        *,
        tenant_id: str,
        job_ids: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        bounded_limit = max(1, min(int(limit), 500))
        selected_ids = [str(item).strip() for item in (job_ids or []) if str(item).strip()]
        if selected_ids:
            target_job_ids = list(dict.fromkeys(selected_ids))[:bounded_limit]
        else:
            records = self._job_store.list_dead_letter_jobs(tenant_id=tenant_id, limit=bounded_limit)
            target_job_ids = [str(item.get("job_id", "")).strip() for item in records if str(item.get("job_id", "")).strip()]

        replayed = 0
        failures: list[dict[str, str]] = []
        for job_id in target_job_ids:
            if self._job_store.replay_dead_letter_job(tenant_id=tenant_id, job_id=job_id):
                replayed += 1
            else:
                failures.append(
                    {
                        "job_id": job_id,
                        "reason_code": "DLQ_REPLAY_NOT_FOUND_OR_NOT_DLQ",
                    }
                )
        with self._lock:
            self._dlq_replayed_total += replayed
            self._dlq_replay_failed_total += len(failures)
        return {
            "attempted": len(target_job_ids),
            "replayed": replayed,
            "failures": failures,
        }

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

    def _record_tenant_cost(
        self,
        *,
        tenant_id: str,
        provider_id: str,
        tool_name: str,
        amount: int,
    ) -> None:
        normalized = str(tenant_id).strip() or "default"
        partition_key, _, _ = self._resolve_partition_limit(
            tenant_id=normalized,
            provider_id=provider_id,
            tool_name=tool_name,
        )
        now = time.time()
        with self._lock:
            self._tenant_cost_microunits_total[normalized] = int(
                self._tenant_cost_microunits_total.get(normalized, 0)
            ) + max(int(amount), 0)
            tenant_partition_totals = self._tenant_partition_cost_microunits_total.setdefault(normalized, {})
            tenant_partition_totals[partition_key] = int(tenant_partition_totals.get(partition_key, 0)) + max(int(amount), 0)
            if self._enable_cost_window_policy:
                started, current = self._window_state_unlocked(tenant_id=normalized, now=now)
                self._tenant_cost_window_started_epoch[normalized] = int(started)
                self._tenant_cost_window_microunits[normalized] = int(current) + max(int(amount), 0)
                partition_started, partition_current = self._partition_window_state_unlocked(
                    tenant_id=normalized,
                    partition_key=partition_key,
                    now=now,
                )
                tenant_partition_window_started = self._tenant_partition_cost_window_started_epoch.setdefault(normalized, {})
                tenant_partition_windows = self._tenant_partition_cost_window_microunits.setdefault(normalized, {})
                tenant_partition_window_started[partition_key] = int(partition_started)
                tenant_partition_windows[partition_key] = int(partition_current) + max(int(amount), 0)

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

    def _cost_limit_exceeded(
        self,
        *,
        tenant_id: str,
        provider_id: str,
        tool_name: str,
    ) -> tuple[bool, str, dict[str, str | int]]:
        normalized = str(tenant_id).strip() or "default"
        partition_key, limit, is_partitioned = self._resolve_partition_limit(
            tenant_id=normalized,
            provider_id=provider_id,
            tool_name=tool_name,
        )
        if limit <= 0:
            return (
                False,
                "",
                {
                    "tenant_id": normalized,
                    "partition_key": partition_key,
                    "partition_limit_microunits": int(limit),
                    "partitioned_policy_applied": int(is_partitioned),
                },
            )
        if self._enable_cost_window_policy:
            _, window_cost = self._partition_window_state(
                tenant_id=normalized,
                partition_key=partition_key,
                now=time.time(),
            )
            return (
                window_cost >= int(limit),
                "BYOC_COST_WINDOW_PARTITION_LIMIT_EXCEEDED" if is_partitioned else "BYOC_COST_WINDOW_LIMIT_EXCEEDED",
                {
                    "tenant_id": normalized,
                    "partition_key": partition_key,
                    "partition_consumed_microunits": int(window_cost),
                    "partition_limit_microunits": int(limit),
                    "partitioned_policy_applied": int(is_partitioned),
                    "window_seconds": int(self._cost_window_seconds),
                },
            )
        with self._lock:
            consumed = int(self._tenant_partition_cost_microunits_total.get(normalized, {}).get(partition_key, 0))
        return (
            consumed >= int(limit),
            "BYOC_COST_PARTITION_LIMIT_EXCEEDED" if is_partitioned else "BYOC_COST_LIMIT_EXCEEDED",
            {
                "tenant_id": normalized,
                "partition_key": partition_key,
                "partition_consumed_microunits": int(consumed),
                "partition_limit_microunits": int(limit),
                "partitioned_policy_applied": int(is_partitioned),
            },
        )

    def _cost_limit_result(
        self,
        call: ToolCallContext,
        *,
        timeout_ms: int,
        tenant_id: str,
        reason_code: str,
        details: dict[str, str | int],
    ) -> ToolResult:
        normalized_reason = str(reason_code).strip() or "BYOC_COST_LIMIT_EXCEEDED"
        self._increment_tenant_rejection(tenant_id=tenant_id, reason_code=normalized_reason)
        merged_details = {"backend_id": self.backend_id, "tenant_id": tenant_id}
        merged_details.update(details)
        return ToolResult(
            schema_version="1.0",
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.ERROR,
            error=NormalizedError(
                code=normalized_reason,
                category="policy",
                message="BYOC tenant cost limit exceeded.",
                retryable=False,
                details=merged_details,
            ),
            execution=ExecutionMetadata(
                mode_used=ToolExecutionMode.DETERMINISTIC,
                timeout_ms=timeout_ms,
            ),
            audit=ToolAudit(correlation_id=call.call_id),
        )

    def _normalize_budget_partition_scope(self, scope: str) -> str:
        normalized = str(scope or "").strip().lower()
        if normalized in {"per_provider", "provider"}:
            return "per_provider"
        if normalized in {"per_tool", "tool"}:
            return "per_tool"
        return "tenant"

    def _normalize_budget_partition_limits(self, raw_limits: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for key, value in raw_limits.items():
            token = str(key).strip().lower()
            if not token:
                continue
            try:
                normalized[token] = max(int(value), 0)
            except (TypeError, ValueError):
                continue
        return normalized

    def _resolve_partition_limit(
        self,
        *,
        tenant_id: str,
        provider_id: str,
        tool_name: str,
    ) -> tuple[str, int, bool]:
        _ = tenant_id
        partition_key = "tenant"
        partition_limit = int(self._cost_limit_microunits_per_tenant)
        is_partitioned = False
        if self._budget_partition_scope == "per_provider":
            provider = str(provider_id or "").strip().lower()
            candidate = f"provider:{provider}" if provider else ""
            if candidate and candidate in self._budget_partition_limits_microunits:
                partition_key = candidate
                partition_limit = int(self._budget_partition_limits_microunits[candidate])
                is_partitioned = True
        elif self._budget_partition_scope == "per_tool":
            tool = str(tool_name or "").strip().lower()
            candidate = f"tool:{tool}" if tool else ""
            if candidate and candidate in self._budget_partition_limits_microunits:
                partition_key = candidate
                partition_limit = int(self._budget_partition_limits_microunits[candidate])
                is_partitioned = True
        return partition_key, max(partition_limit, 0), is_partitioned

    def _partition_limit_for_key(self, partition_key: str) -> int:
        normalized = str(partition_key or "").strip().lower()
        if normalized and normalized in self._budget_partition_limits_microunits:
            return int(self._budget_partition_limits_microunits[normalized])
        return int(self._cost_limit_microunits_per_tenant)

    def _partition_window_state(self, *, tenant_id: str, partition_key: str, now: float) -> tuple[int, int]:
        normalized = str(tenant_id).strip() or "default"
        normalized_partition = str(partition_key).strip().lower() or "tenant"
        with self._lock:
            return self._partition_window_state_unlocked(
                tenant_id=normalized,
                partition_key=normalized_partition,
                now=now,
            )

    def _partition_window_state_unlocked(self, *, tenant_id: str, partition_key: str, now: float) -> tuple[int, int]:
        tenant_started = self._tenant_partition_cost_window_started_epoch.setdefault(tenant_id, {})
        tenant_windows = self._tenant_partition_cost_window_microunits.setdefault(tenant_id, {})
        start = int(tenant_started.get(partition_key, int(now)))
        cost = int(tenant_windows.get(partition_key, 0))
        if start <= 0:
            start = int(now)
        if int(now) - start >= int(self._cost_window_seconds):
            start = int(now)
            cost = 0
            tenant_started[partition_key] = start
            tenant_windows[partition_key] = cost
        else:
            tenant_started.setdefault(partition_key, start)
            tenant_windows.setdefault(partition_key, cost)
        return (start, cost)

    def _window_state(self, *, tenant_id: str, now: float) -> tuple[int, int]:
        normalized = str(tenant_id).strip() or "default"
        with self._lock:
            return self._window_state_unlocked(tenant_id=normalized, now=now)

    def _window_state_unlocked(self, *, tenant_id: str, now: float) -> tuple[int, int]:
        start = int(self._tenant_cost_window_started_epoch.get(tenant_id, int(now)))
        cost = int(self._tenant_cost_window_microunits.get(tenant_id, 0))
        if start <= 0:
            start = int(now)
        if int(now) - start >= int(self._cost_window_seconds):
            start = int(now)
            cost = 0
            self._tenant_cost_window_started_epoch[tenant_id] = start
            self._tenant_cost_window_microunits[tenant_id] = cost
        else:
            self._tenant_cost_window_started_epoch.setdefault(tenant_id, start)
            self._tenant_cost_window_microunits.setdefault(tenant_id, cost)
        return (start, cost)

    def _fair_admission_coordinator(self) -> ByocFairAdmissionCoordinator:
        key = int(self._fair_admission_max_inflight_global)
        with self._coordinator_lock:
            coordinator = self._fair_admission_by_key.get(key)
            if coordinator is None:
                coordinator = ByocFairAdmissionCoordinator(max_inflight_global=key)
                self._fair_admission_by_key[key] = coordinator
            return coordinator

    def _acquire_fair_admission(self, *, tenant_id: str) -> FairAdmissionToken | None:
        return self._fair_admission_coordinator().acquire(
            tenant_id=tenant_id,
            wait_timeout_ms=self._fair_admission_wait_timeout_ms,
        )

    def _fair_admission_timeout_result(
        self,
        call: ToolCallContext,
        *,
        timeout_ms: int,
        tenant_id: str,
    ) -> ToolResult:
        with self._lock:
            self._fair_admission_timeout_total += 1
            self._tenant_fair_admission_timeout_total[tenant_id] = int(
                self._tenant_fair_admission_timeout_total.get(tenant_id, 0)
            ) + 1
        self._increment_tenant_rejection(tenant_id=tenant_id, reason_code="BYOC_FAIR_ADMISSION_TIMEOUT")
        return ToolResult(
            schema_version="1.0",
            call_id=call.call_id,
            tool_name=call.tool_name,
            status=ToolStatus.ERROR,
            error=NormalizedError(
                code="BYOC_FAIR_ADMISSION_TIMEOUT",
                category="policy",
                message="BYOC fair admission wait timeout exceeded.",
                retryable=True,
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
        self._record_tenant_cost(
            tenant_id=tenant_id,
            provider_id=call.provider_id,
            tool_name=call.tool_name,
            amount=self._cost_for_status(status),
        )
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


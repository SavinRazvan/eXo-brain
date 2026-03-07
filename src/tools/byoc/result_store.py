"""
File: result_store.py
Path: src/tools/byoc/result_store.py
Role: BYOC result ingestion/idempotency contracts with in-memory adapters.
Used By:
 - src/tools/byoc/connector_runtime.py
 - src/tools/byoc/sqlite_store.py
Depends On:
 - abc
 - dataclasses
 - threading
Notes:
 - `consume(job_id)` provides one-shot delivery semantics for runtime polling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import threading
import time

from src.tools.byoc.job_contracts import ByocToolResultEnvelope


@dataclass(slots=True)
class ByocResultIngestOutcome:
    accepted: bool
    duplicate: bool
    reason_code: str


@dataclass(slots=True)
class ByocConflictCountRecord:
    strategy: str
    tool_name: str
    tool_version: str
    reason_code: str
    count: int


class ByocResultConflictStrategy(str, Enum):
    FIRST_WRITE_WINS = "first_write_wins"
    LAST_WRITE_WINS = "last_write_wins"
    PREFER_SUCCESS = "prefer_success"


def resolve_result_conflict(
    *,
    existing: ByocToolResultEnvelope,
    incoming: ByocToolResultEnvelope,
    strategy: ByocResultConflictStrategy,
) -> bool:
    """Return True when incoming result should replace existing payload."""
    if strategy == ByocResultConflictStrategy.LAST_WRITE_WINS:
        return True
    if strategy == ByocResultConflictStrategy.PREFER_SUCCESS:
        existing_success = str(existing.status).strip().lower() == "success"
        incoming_success = str(incoming.status).strip().lower() == "success"
        if incoming_success and not existing_success:
            return True
    return False


class ByocResultStore(ABC):
    @abstractmethod
    def ingest(self, result: ByocToolResultEnvelope) -> ByocResultIngestOutcome:
        """Store one result envelope idempotently."""

    @abstractmethod
    def consume(self, job_id: str) -> ByocToolResultEnvelope | None:
        """Consume and remove one stored result envelope for a job."""

    def has_idempotency_key(self, key: str) -> bool:
        """Return True when idempotency key was already ingested."""
        return False

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        """Return retention/queue metrics for one tenant."""
        return {"pending_result_payloads": 0}

    def cleanup_retention(
        self,
        *,
        tenant_id: str,
        result_ttl_seconds: int,
        idempotency_ttl_seconds: int,
        max_result_records: int,
    ) -> dict[str, int]:
        """Prune result payload/idempotency records for one tenant."""
        return {"result_payloads_pruned": 0, "idempotency_pruned": 0}

    def conflict_strategy_name(self) -> str:
        """Return configured conflict strategy name for observability."""
        return "unknown"

    def list_conflict_counts(self, *, tenant_id: str) -> list[ByocConflictCountRecord]:
        """Return conflict counters scoped to one tenant."""
        return []


class ReplayGuard(ABC):
    @abstractmethod
    def mark_once(self, *, key: str, ttl_seconds: int) -> bool:
        """Return True if key is new, False when key is a replay."""

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        """Return replay-guard metrics for one tenant."""
        return {"replay_keys_active": 0}

    def cleanup_retention(self, *, tenant_id: str) -> dict[str, int]:
        """Prune expired replay entries for one tenant."""
        return {"replay_keys_pruned": 0}


class InMemoryByocResultStore(ByocResultStore):
    """Thread-safe in-memory idempotency store for BYOC result callbacks."""

    def __init__(
        self,
        *,
        conflict_strategy: ByocResultConflictStrategy = ByocResultConflictStrategy.FIRST_WRITE_WINS,
    ) -> None:
        self._lock = threading.Lock()
        self._conflict_strategy = conflict_strategy
        self._seen_idempotency_keys: set[str] = set()
        self._results_by_job_id: dict[str, ByocToolResultEnvelope] = {}
        self._conflict_counts: dict[tuple[str, str, str], int] = {}

    def ingest(self, result: ByocToolResultEnvelope) -> ByocResultIngestOutcome:
        key = str(result.idempotency_key).strip()
        if not key:
            return ByocResultIngestOutcome(
                accepted=False,
                duplicate=False,
                reason_code="IDEMPOTENCY_KEY_REQUIRED",
            )
        with self._lock:
            if key in self._seen_idempotency_keys:
                return ByocResultIngestOutcome(
                    accepted=True,
                    duplicate=True,
                    reason_code="IDEMPOTENT_DUPLICATE",
                )
            existing = self._results_by_job_id.get(result.job_id)
            if existing is not None and str(existing.idempotency_key).strip() != key:
                should_replace = resolve_result_conflict(
                    existing=existing,
                    incoming=result,
                    strategy=self._conflict_strategy,
                )
                if not should_replace:
                    self._record_conflict(
                        tenant_id=result.tenant_id,
                        tool_name=result.tool_name,
                        tool_version=result.tool_version,
                        reason_code="BYOC_RESULT_CONFLICT_REJECTED",
                    )
                    return ByocResultIngestOutcome(
                        accepted=False,
                        duplicate=False,
                        reason_code="BYOC_RESULT_CONFLICT_REJECTED",
                    )
                self._seen_idempotency_keys.add(key)
                self._results_by_job_id[result.job_id] = result
                self._record_conflict(
                    tenant_id=result.tenant_id,
                    tool_name=result.tool_name,
                    tool_version=result.tool_version,
                    reason_code="BYOC_RESULT_CONFLICT_REPLACED",
                )
                return ByocResultIngestOutcome(
                    accepted=True,
                    duplicate=False,
                    reason_code="BYOC_RESULT_CONFLICT_REPLACED",
                )
            self._seen_idempotency_keys.add(key)
            self._results_by_job_id[result.job_id] = result
            return ByocResultIngestOutcome(
                accepted=True,
                duplicate=False,
                reason_code="INGESTED",
            )

    def consume(self, job_id: str) -> ByocToolResultEnvelope | None:
        normalized = str(job_id).strip()
        if not normalized:
            return None
        with self._lock:
            return self._results_by_job_id.pop(normalized, None)

    def has_idempotency_key(self, key: str) -> bool:
        normalized = str(key).strip()
        if not normalized:
            return False
        with self._lock:
            return normalized in self._seen_idempotency_keys

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        with self._lock:
            pending = sum(1 for result in self._results_by_job_id.values() if result.tenant_id == normalized)
            seen = sum(1 for key in self._seen_idempotency_keys if key.startswith(f"{normalized}:"))
            return {
                "pending_result_payloads": pending,
                "idempotency_keys_seen": seen,
            }

    def cleanup_retention(
        self,
        *,
        tenant_id: str,
        result_ttl_seconds: int,
        idempotency_ttl_seconds: int,
        max_result_records: int,
    ) -> dict[str, int]:
        # In-memory adapter is process-local and naturally bounded by runtime lifetime.
        return {"result_payloads_pruned": 0, "idempotency_pruned": 0}

    def conflict_strategy_name(self) -> str:
        return str(self._conflict_strategy.value)

    def list_conflict_counts(self, *, tenant_id: str) -> list[ByocConflictCountRecord]:
        normalized = str(tenant_id).strip()
        if not normalized:
            return []
        out: list[ByocConflictCountRecord] = []
        with self._lock:
            for (tenant, reason_code, tool_key), count in sorted(self._conflict_counts.items()):
                if tenant != normalized:
                    continue
                if "@" in tool_key:
                    tool_name, tool_version = tool_key.rsplit("@", 1)
                else:
                    tool_name, tool_version = tool_key, ""
                out.append(
                    ByocConflictCountRecord(
                        strategy=self._conflict_strategy.value,
                        tool_name=tool_name,
                        tool_version=tool_version,
                        reason_code=reason_code,
                        count=int(count),
                    )
                )
        return out

    def _record_conflict(
        self,
        *,
        tenant_id: str,
        tool_name: str,
        tool_version: str,
        reason_code: str,
    ) -> None:
        tenant = str(tenant_id).strip() or "default"
        tool = str(tool_name).strip() or "unknown_tool"
        version = str(tool_version).strip()
        reason = str(reason_code).strip() or "BYOC_RESULT_CONFLICT_UNKNOWN"
        key = (tenant, reason, f"{tool}@{version}")
        self._conflict_counts[key] = int(self._conflict_counts.get(key, 0)) + 1


class InMemoryReplayGuard(ReplayGuard):
    """In-memory replay guard keyed by nonce/jti with TTL expiry."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._expires_at_epoch: dict[str, float] = {}

    def mark_once(self, *, key: str, ttl_seconds: int) -> bool:
        normalized = str(key).strip()
        if not normalized:
            return False
        ttl = max(int(ttl_seconds), 1)
        now = time.time()
        with self._lock:
            self._cleanup_unlocked(now)
            if normalized in self._expires_at_epoch:
                return False
            self._expires_at_epoch[normalized] = now + ttl
            return True

    def _cleanup_unlocked(self, now: float) -> None:
        stale_keys = [k for k, expiry in self._expires_at_epoch.items() if expiry <= now]
        for key in stale_keys:
            self._expires_at_epoch.pop(key, None)

    def health_metrics(self, *, tenant_id: str) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        prefix = f"{normalized}:"
        with self._lock:
            self._cleanup_unlocked(time.time())
            active = sum(1 for key in self._expires_at_epoch if key.startswith(prefix))
            return {"replay_keys_active": active}

    def cleanup_retention(self, *, tenant_id: str) -> dict[str, int]:
        normalized = str(tenant_id).strip()
        prefix = f"{normalized}:"
        with self._lock:
            now = time.time()
            before = {k for k in self._expires_at_epoch.keys() if k.startswith(prefix)}
            self._cleanup_unlocked(now)
            after = {k for k in self._expires_at_epoch.keys() if k.startswith(prefix)}
        return {"replay_keys_pruned": max(0, len(before) - len(after))}


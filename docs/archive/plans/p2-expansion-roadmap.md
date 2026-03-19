<!--
File: p2-expansion-roadmap.md
Path: docs/archive/plans/p2-expansion-roadmap.md
Role: Historical roadmap snapshot for the retired P2 expansion queue.
Used By:
 - docs/plans/docs-archive-index.md
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
Notes:
 - Retained for traceability only; not an active execution source.
-->

# P2 Expansion Roadmap

> Status: Archived historical roadmap.
> Canonical replacement: `docs/plans/tenant-tool-execution-architecture.md`
> Archived on: 2026-03-19
> Archive reason: superseded

## Purpose

Track execution of post-P1 expansion items in dependency order while keeping deterministic controls and tenant isolation intact.

## Current Slice Outcome

- Implemented BYOC webhook submit baseline:
  - endpoint: `POST /tenants/{tenant_id}/admin/byoc/webhook/jobs/submit`
  - auth: shared webhook secret
  - replay guard: `webhook_request_id`
  - result ingestion path reuses deterministic lease/idempotency/integrity checks.
- Implemented P2-1 autoscaling/backpressure baseline:
  - added `AgentScaler` policy with explicit scale-up and backpressure thresholds
  - wired submission-time scaling decisions into background runtime admission path
  - exposed scheduler/worker-pool scale-up hooks (safe scale-up only; no live scale-down mutation)
  - added deterministic unit/integration coverage for scale-up and backpressure rejection behavior
- Implemented P2-2 DLQ/replay baseline for BYOC:
  - lease-expiry retries now route jobs to dead-letter when claim-attempt threshold is exhausted
  - added BYOC admin APIs to list dead-letter jobs and replay one dead-lettered job back into queue
  - added runtime/API coverage for end-to-end dead-letter then replay completion path
- Implemented P2-3 conflict-resolution baseline for BYOC result ingestion:
  - added strategy-driven conflict resolution (`first_write_wins`, `last_write_wins`, `prefer_success`)
  - added runtime setting/env wiring for conflict strategy selection
  - enforced deterministic conflict outcomes with explicit reason codes for reject/replace paths
- Implemented P2-4 fine-grained tenancy/cost governance instrumentation baseline:
  - added tenant-scoped cost counters and configurable per-status BYOC cost units
  - added optional enforcement gate (`EXO_BYOC_ENFORCE_COST_LIMIT`) with deterministic rejection code
  - exposed tenant-level governance counters in runtime-control stats for dashboard/alerting
  - expanded operations dashboard guidance with governance panels and alert thresholds

## Remaining P2 Expansion Queue

- No open P2 expansion items in this roadmap. Next queue should be sourced from a fresh backlog reconciliation slice.

## Acceptance Gates

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`
- update canonical plan/tracker references after each merged slice.

# P2 Expansion Roadmap

## Purpose

Track execution of post-P1 expansion items in dependency order while keeping deterministic controls and tenant isolation intact.

## Current Slice Outcome

- Implemented BYOC webhook submit baseline:
  - endpoint: `POST /tenants/{tenant_id}/admin/byoc/webhook/jobs/submit`
  - auth: shared webhook secret
  - replay guard: `webhook_request_id`
  - result ingestion path reuses deterministic lease/idempotency/integrity checks.

## Remaining P2 Expansion Queue

1. Autoscaling policy implementation (`AgentScaler`) with explicit backpressure thresholds.
2. Dead-letter queue policy and replay/retry workflow.
3. Advanced result conflict-resolution strategies in aggregator paths.
4. Fine-grained tenancy and cost governance instrumentation.

## Acceptance Gates

- `python -m pytest -q`
- `python scripts/architecture/validate_layers.py`
- `python scripts/architecture/scan_forbidden_imports.py`
- update canonical plan/tracker references after each merged slice.

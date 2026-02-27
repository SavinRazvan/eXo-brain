# Persistence Module and Hybrid DB Strategy

## Goal
Make persistence a first-class module so the framework can run consistently with local databases, remote self-hosted databases, or managed cloud databases.

## Why This Is Mandatory
The architecture requires durable persistence for:
- session continuity
- checkpoint/resume for background multi-agent jobs
- workflow storage/load
- audit trail and compliance evidence
- event/timeline reconstruction for debugging

Without a dedicated persistence module, reliability and enterprise controls are incomplete.

## Module Boundary

Proposed package:
```text
src/persistence/
  contracts.py
  session_store.py
  checkpoint_store.py
  workflow_store.py
  audit_store.py
  event_store.py
  adapters/
    postgres_adapter.py
    sqlite_adapter.py
  factory.py
```

Core rule:
- Orchestration code uses store interfaces only.
- Backend selection happens through config/profile and factory wiring.

## Store Contracts (Minimum)
- `SessionStore`
  - `save_session(...)`
  - `load_session(...)`
- `CheckpointStore`
  - `save_checkpoint(...)`
  - `load_latest_checkpoint(...)`
- `WorkflowStore`
  - `save_workflow(...)`
  - `load_workflow(...)`
- `AuditStore`
  - `append_audit_event(...)`
  - `query_audit_events(...)`
- `EventStore`
  - `append_event(...)`
  - `query_events(...)`

## Hybrid Profile Strategy
- `local/dev`: `sqlite` adapter for fast local setup and tests.
- `self_hosted`: `postgres` adapter against enterprise-hosted DB.
- `managed_cloud`: `postgres` adapter against managed DB service.

All profiles must preserve:
- schema compatibility
- transaction behavior for critical writes
- tenant isolation guarantees

## Data Safety and Security Requirements
- encrypt in transit for all DB connections
- credential retrieval only via secrets provider abstraction
- audit-critical writes must be durable and timestamped
- retention and purge policies must be configurable per environment

## Performance and Reliability Requirements
- checkpoint writes must be atomic
- retry policy for transient DB failures with idempotency controls
- bounded connection pools and backpressure for saturation conditions
- migration strategy must be repeatable and reversible

## Validation Checklist
- contract tests for each store interface
- adapter parity tests (`sqlite` vs `postgres`) for core workflows
- failure-path tests (disconnects/timeouts/partial failures)
- concurrency tests for parallel checkpoint and audit writes
- security tests for tenant isolation and access control

## Rollout Recommendation
1. Implement contracts and `sqlite` adapter first (developer velocity).
2. Add `postgres` adapter and run parity test suite.
3. Enable managed/self-hosted profile selection through config.
4. Lock persistence behavior after vertical-slice evidence passes.

## Related Docs
- `02-target-architecture.md`
- `08-module-requirements-matrix.md`
- `12-bootstrap-checklist.md`
- `25-technology-stack-decisions.md`
- `26-deployment-profiles-matrix.md`
- `27-reference-tech-stack-lock-v1.md`

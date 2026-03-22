<!--
File: logging-and-errors.md
Path: docs/operations/logging-and-errors.md
Role: Phased rollout plan for module-wide error handling and logging standardization.
Used By:
 - Observability and implementation planning
Depends On:
 - src/observability/*
 - src/* module boundaries
Notes:
 - Keep migration incremental and reversible. Do not force all-module big-bang rewrites.
-->

# Logging and error-handling rollout

## Goal
- Add consistent error handling and structured logging across all module groups without destabilizing runtime behavior.

## Constraints
- Preserve provider-neutral adapter wall.
- Preserve deterministic execution and policy gates.
- Keep rollout incremental by module slice, with fallback to existing logger path.

## Phase plan

### Phase 1: Standards
- Define module-level error taxonomy (reason codes + category + severity).
- Define required log fields (`correlation_id`, `tenant_id`, `module`, `event`, `status`, `reason_code`).
- Add baseline guidelines for when to log info/warn/error and when to escalate.

### Phase 2: Technical spike (Hydra-logger candidate)
- Evaluate fit for:
  - structured logging
  - async and composite logger support
  - policy-driven routing
  - performance overhead under runtime load
- Produce decision:
  - `adopt`
  - `adopt_with_adapter`
  - `reject_for_now`

### Phase 3: Controlled rollout
- Start with low-risk modules (`observability`, `config`, selected `api` surfaces).
- Expand to execution-critical modules (`core`, `tools`, `runtime`) only after gate pass.
- Keep rollback switch to current logging path until confidence is proven.

## Acceptance gates
- No regression in architecture fitness scripts.
- Target module test suites remain green.
- Logging fields required by audit/evidence pipelines are preserved.
- Throughput and latency impact remains within agreed threshold.

## Status
- `planned` (spike and standards definition pending).

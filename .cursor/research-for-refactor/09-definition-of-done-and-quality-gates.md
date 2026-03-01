# Definition of Done and Quality Gates

## Goal
Standardize release readiness for architecture and implementation phases.

## Definition of Done (Per Milestone)
- Interfaces documented and implemented.
- Tests pass for functional and failure paths.
- Structured logs/traces/metrics emitted with correlation IDs.
- Rollback strategy documented and verified.
- Security/policy behavior validated for state-changing/high-impact operations.

## Quality Gates

## Gate A: Architecture Completeness
- Required docs exist:
  - target architecture
  - module requirements matrix
  - agent orchestration plan
- No unresolved critical unknowns.

## Gate B: Runtime Correctness
- Background runtime handles:
  - submit
  - cancel
  - resume
  - completion
- Sequential and parallel modes both validated.

## Gate C: Tooling and Plugin Safety
- Plugin lifecycle tests pass (`load`, `unload`, `reload`, compatibility).
- State-changing/high-impact tools blocked/escalated per policy rules.
- Deterministic runtime path validated for side-effecting operations.

## Gate D: Observability and Debugability
- Timeline reconstruction works for parallel jobs.
- Logs queryable by `job_id`, `task_id`, `agent_id`, `tool_name`.
- Failure case can be debugged end-to-end from logs.

## Gate E: Performance and Stability
- Concurrency limits respected under load.
- Retry and fallback behavior deterministic.
- No critical regressions against baseline SLO/SLA targets.

## Gate F: Portability
- Core module remains embeddable.
- No hard dependency on specific UI or transport.
- Host adapter examples compile and run.

## Gate G: Anti-Monolith Architecture Fitness
- No provider SDK imports outside adapter modules.
- No cross-layer shortcuts that bypass policy middleware.
- Static dependency check confirms allowed import directions only.
- No new "god module" that combines orchestration + provider + tool + policy responsibilities.
- Plugin/adapter additions require no core orchestrator rewrite.

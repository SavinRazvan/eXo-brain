# Implementation Coding Standards (Execution Phase)

## Goal
Translate architecture plans into consistent production code with strict modular boundaries, reliability, and debuggability.

## Mandatory Standards
- Keep core embeddable: no mandatory UI/API/CLI coupling.
- Enforce interface-first module contracts before implementation.
- Use dependency injection for adapters, policies, tools, and storage providers.
- Standardize structured errors and output envelopes across modules.
- Require explicit timeout/retry/idempotency behavior for external calls.
- Emit structured logs and correlation IDs for all runtime paths.

## Module Boundary Rules
- `core/` orchestrates only; no provider-specific logic.
- `runtime/` implements provider adapters and capability mapping.
- `tools/` executes deterministic tool runtime + plugin hooks.
- `policies/` owns allow/deny/escalate decisions and risk gates.
- `observability/` owns logs, traces, metrics, and timeline reconstruction.

## Quality Requirements Per Change
- unit tests for new logic
- integration tests for cross-module behavior
- failure-path tests for timeout/error/fallback scenarios
- updated docs/contracts where interfaces changed

## Definition of Good PR
- scope is module-contained
- interface impact is explicit
- rollback path documented
- test evidence attached
- no hidden architecture drift

## Related Docs
- `08-module-requirements-matrix.md`
- `09-definition-of-done-and-quality-gates.md`
- `16-enterprise-testing-strategy.md`

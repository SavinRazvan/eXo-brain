<!--
File: workspace-architecture.md
Path: docs/architecture/workspace-architecture.md
Role: Durable workspace architecture notes (adapter portability, deterministic execution, enterprise controls).
Used By:
 - AGENTS.md, implementer profile, local planning stubs
Depends On:
 - AGENTS.md
 - .cursor/rules/provider-neutral-adapter-wall.mdc
Notes:
 - Live execution trackers stay under `.local/index-and-planning/current/`; edit this file for enduring doctrine.
-->

# Workspace architecture notes

## Non-negotiable boundaries
- Core orchestration stays provider-neutral.
- Provider SDK behavior remains behind runtime adapters.
- Customer-owned provider credentials and provider-native adapter configuration stay outside the core governance boundary.
- Policy middleware remains in the execution path for all state-changing operations.
- `platform_bootstrap` is the only composition root; application modules must depend on facades, not raw `app.state` objects.

## Modular monolith contract
- `identity_access` owns authentication, API keys, RBAC, and platform-admin trust boundaries.
- `tenant_governance` owns overlays, rate limits, quotas, entitlements, and fairness controls.
- `provider_management` owns provider registration, protocol typing, health checks, and adapter lookup.
- `agent_management` owns durable agent definitions and their public contracts.
- `tool_management` owns tool metadata, versions, artifacts, and upload governance inputs.
- `session_runtime` owns tenant context lookup, session creation, run control, and runtime caches.
- `turn_execution` owns orchestration flow, mode selection, progress semantics, and host-adapter seams.
- `audit_observability` owns audit persistence, signed export/verify settings, logs, metrics, tracing sinks, and standard telemetry export adapters.
- `platform_bootstrap` owns settings validation, default bootstrap provider wiring, module installation, and startup hydration.
- `shared_kernel` stays limited to immutable schemas and shared reason-code contracts.
- `adapter_contracts` owns runtime/execution adapter interfaces only.

## Allowed dependency direction
- `shared_kernel` depends on nothing.
- `adapter_contracts` may depend only on `shared_kernel`.
- `identity_access`, `agent_management`, and `audit_observability` may depend only on `shared_kernel`.
- `tenant_governance` may depend on `shared_kernel`, `identity_access`, and `audit_observability`.
- `provider_management` may depend on `shared_kernel`, `identity_access`, and `adapter_contracts`.
- `tool_management` may depend on `shared_kernel`, `tenant_governance`, and `audit_observability`.
- `turn_execution` may depend on `shared_kernel`, `tenant_governance`, `audit_observability`, `adapter_contracts`, and `tool_management`.
- `session_runtime` may depend on `shared_kernel`, `agent_management`, `tool_management`, `provider_management`, `tenant_governance`, `adapter_contracts`, and `turn_execution`.
- `platform_bootstrap` may compose all modules but must not leak their concrete internals back out as the primary app contract.

## Adapter independence model
- Adapters are loadable by class reference (factory/registry path only).
- Each adapter owns its provider-specific configuration schema.
- Core depends on adapter contracts, not provider names.

## Enterprise requirements
- Versioned adapter contract compatibility check at load time.
- Capability handshake for routing (capability + policy, never provider hardcoding).
- Config validation before provider registration and before startup hydration.
- Deterministic tool governance preserved regardless of adapter selection.
- OpenTelemetry/Prometheus interoperability belongs behind `audit_observability`; exporter failure must not affect governed execution safety.

## Resource consumption controls
- Execution placement policy: hosted/byoc/blocked.
- Budget and quota gates before expensive tool calls.
- Tenant fairness/rate/concurrency controls with structured reason codes.

## Open questions
- Do we require signed adapters for all profiles or enterprise-only profiles?
- What minimum compatibility matrix is required for external adapter packages?

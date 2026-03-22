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
- Policy middleware remains in the execution path for all state-changing operations.

## Adapter independence model
- Adapters are loadable by class reference (factory/registry path only).
- Each adapter owns its provider-specific configuration schema.
- Core depends on adapter contracts, not provider names.

## Enterprise requirements
- Versioned adapter contract compatibility check at load time.
- Capability handshake for routing (capability + policy, never provider hardcoding).
- Config validation before provider registration and before startup hydration.
- Deterministic tool governance preserved regardless of adapter selection.

## Resource consumption controls
- Execution placement policy: hosted/byoc/blocked.
- Budget and quota gates before expensive tool calls.
- Tenant fairness/rate/concurrency controls with structured reason codes.

## Open questions
- Do we require signed adapters for all profiles or enterprise-only profiles?
- What minimum compatibility matrix is required for external adapter packages?

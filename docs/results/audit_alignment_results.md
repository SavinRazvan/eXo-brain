# Audit Alignment Results

## Metadata
- Date: 2026-03-01
- Scope: roadmap, research, implementation, tests, workflow rules/skills
- Mode: advisory-only
- Sources:
  - `docs/roadmap/*`
  - `.cursor/research-for-refactor/*`
  - `.cursor/PORTABLE_PACK.md`
  - `src/*`
  - `tests/modules/*`
  - `.agents/*`, `.cursor/rules/*`, `.cursor/skills/*`, `.local/*`

## Executive Summary
- Total findings: 31
- P0: 1
- P1: 24
- P2: 6

Primary risk is persistence tenant-isolation consistency. Most other findings are alignment, traceability, and test-coverage gaps between docs/research and implemented modules.

## Highest Priority Finding
- `AA-persistence-002` (`P0`)
  - Category: `policy_conflict`
  - Source: `src/persistence/contracts.py`, `src/persistence/adapters/sqlite.py`, `src/persistence/adapters/postgres.py`
  - Target: `.cursor/research-for-refactor/08-module-requirements-matrix.md`
  - Issue: Session/checkpoint persistence flows are not consistently tenant-scoped.
  - Recommendation: Add tenant-scoped persistence contract methods and adapter-level tenant isolation with negative cross-tenant tests.

## Findings by Module Group

### Core
- Count: 5 (`P1`: 5)
- Highlights:
  - Boundary validation gaps in context/session handling.
  - Generic exceptions in lifecycle paths instead of stable typed envelopes.
  - Event router coverage missing for important behavior paths.

### Runtime
- Count: 3 (`P1`: 3)
- Highlights:
  - `openai_agents_runtime` lacks error-normalization parity with other adapters.
  - Missing malformed-input and failure-envelope coverage.

### Tools + Policies
- Count: 5 (`P1`: 4, `P2`: 1)
- Highlights:
  - Descriptor/payload validation not strict enough.
  - Post-policy checks are pass-through in key paths.
  - Missing observability assertions for execution metadata.

### MCP
- Count: 5 (`P1`: 3, `P2`: 2)
- Highlights:
  - Timeout/retry enforcement needs explicit implementation.
  - Missing structured observability events for trust/health decisions.
  - Minor doc/header drift around network adapter references.

### Identity + Access Control
- Count: 4 (`P1`: 2, `P2`: 2)
- Highlights:
  - Token validation/rotation contract not explicit.
  - Access model lacks plugin-scoped permission dimension.
  - Some header relation paths are stale.

### Tenancy + Secrets
- Count: 5 (`P1`: 2, `P2`: 3)
- Highlights:
  - Tenant policy overlays defined but not wired into active enforcement path.
  - Secrets failure-path test coverage is incomplete.
  - Stale `Used By` references in headers.

### Persistence
- Count: 7 (`P0`: 1, `P1`: 6)
- Highlights:
  - Tenant scoping conflict (P0).
  - Profile-aware persistence factory behavior incomplete.
  - Missing failure-path/concurrency coverage for persistence guarantees.

### Resilience
- Count: 6 (`P1`: 4, `P2`: 2)
- Highlights:
  - DLQ and compensation hooks lack policy-gate and structured logging integration.
  - Compensation hooks not integrated/tested in runtime paths.
  - Header traceability metadata needs cleanup.

### Agents
- Count: 4 (`P1`: 3, `P2`: 1)
- Highlights:
  - Agents module hardening slice is not explicitly tracked in roadmap phases.
  - Plugin lifecycle operations need policy/audit hooks.
  - Reload plugin path coverage is incomplete.

### Observability + Audit + Compliance
- Count: 4 (`P1`: 2, `P2`: 2)
- Highlights:
  - Evidence bundle schema lacks explicit artifact links expected by release template.
  - Correlation ID coverage does not fully assert job/task/agent/tool propagation.
  - Minor stale header references.

### Integration + Config + Schemas
- Count: 5 (`P1`: 5)
- Highlights:
  - Some docs expect stricter typed schemas than current dictionary-heavy boundaries.
  - Config schema validation coverage gaps.

### Cross-Source Roadmap/Research Drift
- Count: 4 (`P1`: 3, `P2`: 1)
- Highlights:
  - Legacy test path references (`tests/integration`, etc.) remain in research docs.
  - Stale blueprint/scaffold references to non-current file layout and CI file names.

## Recommended Remediation Order
1. Fix `P0` persistence tenant isolation (`AA-persistence-002`) first.
2. Runtime + MCP: normalize error/timeout/retry behavior and contracts.
3. Tools/Policies: strict validation and post-check enforcement.
4. Agents: lifecycle policy/audit integration and reload coverage.
5. Docs/research drift cleanup batch to prevent future implementation mismatch.

## Accepted/Deferred Notes
- Local merge artifact staleness can be lifecycle-scoped and regenerated per active merge phase.
- Historical research docs may remain if clearly labeled as historical and excluded from source-of-truth behavior guidance.

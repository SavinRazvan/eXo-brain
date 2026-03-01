<!--
File: audit_alignment_action_plan.md
Path: docs/results/audit_alignment_action_plan.md
Role: Actionable remediation plan derived from alignment audit findings.
Used By:
 - .agents/skills/review-pr/SKILL.md
 - .agents/skills/prepare-pr/SKILL.md
 - .agents/skills/merge-pr/SKILL.md
Depends On:
 - docs/results/audit_alignment_results.md
 - .local/alignment-audit.md
 - .local/alignment-todos.md
Notes:
 - This plan is execution-oriented and must stay aligned with advisory audit outputs.
-->

# Audit Alignment Action Plan

## Metadata
- Date: 2026-03-01
- Source decisions: `1A, 2A, 3A, 4A, 5A, 6A, 7A`
- Policy posture:
  - Immediate P0 remediation
  - Enforce mode for state-changing/high-impact operations in production
  - Strict priority-map validation (`ValueError` on unknown roles)
  - Precedence: `rules/AGENTS` > roadmap > research > historical notes
  - Small PR slices (1-2 findings per PR)
  - Finding closure tied to PR + evidence links
  - Accepted divergences tracked with expiry/review date

## Execution Order (Approved)
1. Slice 1: P0 persistence tenant isolation fix
2. Slice 2: Runtime + MCP deterministic error/timeout/retry normalization
3. Slice 3: Tools + policies hardening for state-changing/high-impact operations
4. Slice 4: Agents lifecycle policy/audit integration
5. Slice 5: Governance/docs/research drift closure

## Global Constraints
- No monolith changes: each PR addresses 1-2 findings maximum.
- Maintain provider-neutral boundaries and deterministic tool safety.
- Required gates per slice:
  - `python -m pytest -q`
  - `python scripts/architecture/validate_layers.py`
  - `python scripts/architecture/scan_forbidden_imports.py`
- Required artifacts:
  - `.local/review.md`
  - `.local/prep.md`
  - `.local/merge.md`
  - `.local/alignment-audit.md` and `.local/alignment-todos.md` for architecture-impacting slices

---

## Slice 1 - P0 Persistence Tenant Isolation (Blocking)

### Scope
- Add strict tenant-scoped persistence contracts for session/checkpoint/audit paths.
- Enforce tenant filters and isolation in persistence adapters.
- Add structured deny errors for cross-tenant attempts.
- Ensure correlation IDs and tenant metadata are present in persistence logs.

### Target Areas
- `src/persistence/contracts.py`
- `src/persistence/adapters/sqlite.py`
- `src/persistence/adapters/postgres.py`
- relevant persistence call sites that pass tenant context

### Tasks
1. Extend persistence contracts with explicit tenant-scoped method signatures.
2. Enforce tenant matching for all read/write/delete operations in adapters.
3. Add deterministic error envelopes for cross-tenant violations.
4. Propagate tenant context and correlation IDs end-to-end.
5. Add negative tests for cross-tenant read/write attempts.

### Test Matrix
- Positive:
  - same-tenant create/read/update/delete succeeds.
- Negative:
  - cross-tenant reads fail with deterministic structured error.
  - cross-tenant writes fail with deterministic structured error.
- Reliability:
  - concurrent tenant operations do not leak or cross-read.
- Regression:
  - single-tenant baseline flows remain functional.

### Acceptance
- `AA-persistence-002` closed with evidence.
- No cross-tenant leakage in tests.
- All required gates green.

### Rollback/Fallback
- Temporary config fallback to strict read isolation while preserving write safety under emergency conditions.

---

## Slice 2 - Runtime + MCP Deterministic Error/Timeout/Retry Normalization

### Scope
- Normalize runtime adapter error envelopes.
- Enforce timeout and bounded retry behavior in MCP paths.
- Emit structured observability events for retries, timeouts, and health/trust decisions.

### Target Areas
- runtime adapter implementations
- MCP adapter/client execution paths
- observability logging/event emission for runtime/MCP decisions

### Tasks
1. Standardize adapter error normalization for malformed input and execution failures.
2. Enforce explicit timeout + bounded retry policy in MCP operations.
3. Align decision logging fields (`correlation_id`, `tenant_id`, operation classification, decision code).
4. Add deterministic replay coverage for normalized failure paths.

### Test Matrix
- Contract:
  - all adapters emit normalized error envelopes for equivalent failures.
- Integration:
  - MCP timeout behavior is deterministic.
  - retries stop at configured limits.
  - success-after-retry path behaves consistently.
- Replay:
  - same failure input produces same output envelope.

### Acceptance
- Runtime and MCP parity verified by tests.
- Timeout/retry behavior deterministic and observable.

### Rollback/Fallback
- Lower-environment toggle for legacy retry profile only (no production downgrade without approval).

---

## Slice 3 - Tools + Policies Hardening (State-Changing/High-Impact Ops)

### Scope
- Strict descriptor and payload validation before execution.
- Enforce policy post-checks as blocking for protected operations.
- Keep least-privilege read-only paths available.

### Target Areas
- tool descriptor parsing/validation paths
- policy middleware enforcement hooks
- deterministic tool execution path for protected operations

### Tasks
1. Tighten schema validation for tool descriptors/payloads.
2. Make policy decision checkpoints blocking for state-changing/high-impact operations.
3. Ensure deterministic execution envelope is mandatory for protected operations.
4. Strengthen observability assertions around policy checkpoints.

### Test Matrix
- Authorization matrix:
  - allow/deny/escalate outcomes by identity + role + operation class.
- Validation:
  - malformed payloads and invalid descriptors fail fast.
- Observability:
  - policy checkpoint events include required metadata.
- Regression:
  - low-risk read-only operations remain functional.

### Acceptance
- No protected operation executes without explicit policy decision.
- Deterministic path enforced for state-changing/high-impact operations.

### Rollback/Fallback
- Audit-only mode available in lower environments for staged rollout.

---

## Slice 4 - Agents Lifecycle Policy + Audit Integration

### Scope
- Apply policy + audit hooks to plugin lifecycle (`load`, `unload`, `reload`).
- Preserve deterministic handoff/routing behavior under plugin churn.

### Target Areas
- agent lifecycle orchestration and plugin management
- audit/event records for lifecycle operations
- fallback/routing decision traces

### Tasks
1. Add explicit policy checks and reason codes for lifecycle actions.
2. Emit audit records for lifecycle changes and routing decisions.
3. Add missing reload path validation and failure/recovery handling tests.
4. Verify deterministic fallback behavior with concurrent plugin state changes.

### Test Matrix
- Lifecycle authorization:
  - allow/deny/escalate for load/unload/reload.
- Reliability:
  - reload failure recovery is deterministic.
- Routing:
  - fallback target selection remains deterministic during lifecycle changes.

### Acceptance
- Lifecycle operations are policy-guarded and auditable.
- Deterministic routing remains stable under churn scenarios.

### Rollback/Fallback
- Temporarily disable `reload` while keeping load/unload stable if needed.

---

## Slice 5 - Governance/Docs/Research Drift Closure

### Scope
- Apply source-of-truth precedence consistently.
- Remove stale references and align module traceability.
- Maintain accepted divergence registry with expiry.

### Target Areas
- roadmap and research references
- workflow/rules/skills alignment docs
- path/CI/test references and module ownership sections

### Tasks
1. Update stale file/path/workflow references.
2. Align docs with active module/test layout and enforced gates.
3. Add or refresh accepted divergence entries with owner + expiry/review date.
4. Ensure PR workflow docs reference alignment audit artifacts where required.

### Test/Validation Matrix
- Documentation integrity:
  - links/paths resolve correctly.
- Governance consistency:
  - rules, skills, and workflow guidance agree on gates/artifacts.
- Traceability:
  - each high-priority module maps roadmap -> implementation -> tests.

### Acceptance
- No unresolved P1 drift in active source-of-truth documents.
- Accepted divergences explicitly tracked and time-bounded.

### Rollback/Fallback
- Historical docs retained only when clearly marked non-authoritative.

---

## Finding Lifecycle Tracking Standard

For each finding tracked in `.local/alignment-todos.md`, maintain:
- `status`: `open | in_progress | fixed | deferred | accepted`
- `owner`: GitHub username
- `slice`: remediation slice ID
- `pr_link`: pull request URL
- `evidence_link`: artifact reference (`.local/review.md`, `.local/prep.md`, test output)
- `last_updated`: date
- `review_due` (required for `accepted` divergences)

## Initial Finding-to-Slice Mapping
- Slice 1:
  - `AA-persistence-002` (P0) + tightly coupled persistence isolation findings
- Slice 2:
  - runtime error normalization + MCP timeout/retry parity findings
- Slice 3:
  - policy/tool validation and post-check enforcement findings
- Slice 4:
  - agents lifecycle policy/audit/reload coverage findings
- Slice 5:
  - roadmap/research/workflow/path drift findings

## Definition of Done (Plan-Level)
- P0 findings: zero open.
- P1 findings: either fixed or explicitly accepted with expiry and owner.
- All slices completed through PR workflow with green required gates.
- Alignment artifacts updated and internally consistent.

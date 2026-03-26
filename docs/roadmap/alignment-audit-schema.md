<!--
File: alignment-audit-schema.md
Path: docs/roadmap/alignment-audit-schema.md
Role: Required fields and taxonomy for advisory alignment audit findings (.local/workflow-artifacts/alignment/).
Used By:
 - .cursor/skills/enterprise-architecture-audit/SKILL.md
 - enterprise-auditor alignment passes
Depends On:
 - docs/strategy/traceability-matrix.md
Notes:
 - For product-boundary drift (control plane, customer bridge, provider runtime adapter), cite governed-execution-positioning + control-plane-product-alignment-plan as target paths.
-->

# Alignment Audit Schema

## Purpose
Standardize advisory audit findings so outputs from skills, rules checks, and manual review can be merged into one deterministic report.

**Product vocabulary:** When findings involve customer integration or monetization claims, reconcile with [`docs/strategy/governed-execution-positioning.md`](../strategy/governed-execution-positioning.md), [`docs/plans/control-plane-product-alignment-plan.md`](../plans/control-plane-product-alignment-plan.md), and [`docs/api/customer-api-integration-guide.md`](../api/customer-api-integration-guide.md) as well as `traceability-matrix.md`.

## Finding Object (Required Fields)

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | yes | Unique stable ID for finding (`AA-<domain>-<number>`). |
| `severity` | `P0 \| P1 \| P2` | yes | Priority classification. |
| `category` | `string` | yes | Drift class from allowed taxonomy below. |
| `source_path` | `string` | yes | Path where mismatch is observed. |
| `target_path` | `string` | yes | Path that defines expected behavior. |
| `evidence` | `string` | yes | Concise quote or factual mismatch proof. |
| `recommendation` | `string` | yes | Concrete remediation guidance. |
| `status` | `open \| accepted_divergence \| fixed \| deferred` | yes | Lifecycle state. |
| `owner` | `string` | no | Responsible person or role. |
| `due_slice` | `string` | no | Planned implementation slice. |

## Severity Taxonomy

- `P0`: Critical policy, safety, or architecture drift that can enable unsafe behavior or break mandatory workflow gates.
- `P1`: Significant consistency drift with moderate delivery risk (stale docs, conflicting workflow guidance, missing integration traceability).
- `P2`: Minor clarity, naming, or housekeeping drift with low immediate operational risk.

## Allowed Categories

- `stale_doc_reference`
- `policy_conflict`
- `workflow_gate_drift`
- `artifact_requirement_gap`
- `module_traceability_gap`
- `ci_path_drift`
- `naming_or_precedence_drift`
- `strategy_product_boundary_drift` — conflicts with control plane / integration-surface definitions in `docs/strategy/*` or `control-plane-product-alignment-plan.md`
- `test_coverage_mapping_gap`
- `rule_parser_or_format_risk`

## Canonical Outputs

- `.local/workflow-artifacts/alignment/alignment-audit.md`
- `.local/workflow-artifacts/alignment/alignment-todos.md`

## Precedence Rule (When Sources Conflict)

Use this order for expected behavior:

1. `.cursor/rules/*` and `AGENTS.md`
2. `.agents/skills/PR_WORKFLOW.md` and phase skills
3. `docs/roadmap/*`
4. `docs/*` architecture references
5. `docs/archive/*` (supporting/historical unless explicitly promoted)

## Minimal JSON Example

```json
{
  "id": "AA-policy-001",
  "severity": "P1",
  "category": "artifact_requirement_gap",
  "source_path": "docs/roadmap/module-hardening-slice-checklist.md",
  "target_path": ".cursor/rules/pr-workflow-enforcement.mdc",
  "evidence": "Checklist requires review/prep artifacts but omits merge artifact.",
  "recommendation": "Add merge artifact requirement and attribution fields.",
  "status": "open",
  "owner": "platform-architecture",
  "due_slice": "feature/advisory-audit-alignment-agent"
}
```

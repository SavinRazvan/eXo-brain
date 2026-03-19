# Documentation Inventory for Notebook Cleanup

## Impacted Documents

| Document | Current Notebook Guidance | Issue | Update Action |
|---|---|---|---|
| `README.md` | Mentions notebooks only indirectly in architecture diagram client labels | No canonical notebook runbook table | Add "Notebook validation suite" section with explicit canonical + module mapping |
| `docs/plans/docs-and-notebooks-cleanup-plan.md` | Defines target state | None | Keep as execution plan and reference implementation artifacts |
| `docs/plans/api-platform.md` | Contains historical notes about notebook-based OpenAI wiring | Can be read as pre-migration implementation state | Keep architecture history, add concise note that canonical execution notebooks moved to new suite |
| `docs/operations/release-candidate-signoff-checklist.md` | No direct notebook runbook guidance | N/A | No change needed for this slice |
| `docs/archive/operations/local-ui-readiness-smoke.md` | Historical UI doc, archived | N/A | No change needed |
| `docs/operations/byoc-failure-injection-playbook.md` | No notebook references | N/A | No change needed |

## Canonical Guidance Target

- One canonical idea-validation entrypoint: `notebooks/01_idea_validation.ipynb`.
- Module-focused notebook checks:
  - `notebooks/10_core_orchestrator_checks.ipynb`
  - `notebooks/11_policy_middleware_checks.ipynb`
  - `notebooks/12_runtime_adapter_checks.ipynb`
  - `notebooks/13_tenant_and_limits_checks.ipynb`

## Acceptance Mapping

- Every document that mentions notebook usage points to the new canonical list.
- No active doc should recommend running legacy brick notebooks first.

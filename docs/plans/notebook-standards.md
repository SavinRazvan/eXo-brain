# Notebook Standards and Ownership Map

## Canonical Notebook Contract (`01_idea_validation.ipynb`)

- **Goal:** prove deterministic tool execution with one end-to-end interaction.
- **Required sections:**
  - prerequisites and API-key marker
  - local deterministic smoke (no API key)
  - single live workflow run (API key required)
  - explicit "intercepted tool call" output proof
  - expected output checklist
- **Rule:** one user prompt -> one model run -> one final result path.

## Module Notebook Template

Every module notebook must include:

1. **Purpose** (what subsystem it validates)
2. **Prerequisites** (env vars, dependencies, API key requirement)
3. **Setup cell** (imports + path bootstrap)
4. **Run/check cell(s)** with assertions
5. **Troubleshooting cell** (common failure causes and next checks)

## Naming Standard

- Canonical: `01_idea_validation.ipynb`
- Module checks: `1x_*_checks.ipynb`
- Keep names stable for docs and onboarding links.

## Ownership Map

| Notebook | Primary Validation Owner | Secondary Owner |
|---|---|---|
| `notebooks/01_idea_validation.ipynb` | Runtime/Tools integration | Platform API maintainers |
| `notebooks/10_core_orchestrator_checks.ipynb` | Core orchestration maintainers | Runtime maintainers |
| `notebooks/11_policy_middleware_checks.ipynb` | Policy and safety maintainers | Core maintainers |
| `notebooks/12_runtime_adapter_checks.ipynb` | Runtime adapter maintainers | Integration maintainers |
| `notebooks/13_tenant_and_limits_checks.ipynb` | Tenancy and control-plane maintainers | API maintainers |

## Expected Output Quality

- Assertions should fail fast with clear messages.
- Tool-execution proof logs should be concise and deterministic.
- API-key-required cells must start with explicit skip guards when key is absent.

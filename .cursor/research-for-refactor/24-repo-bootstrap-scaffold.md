# Repo Bootstrap Scaffold (Essential)

## Goal
Provide a minimal, repeatable scaffold plan to initialize the new repository with the agreed architecture and governance defaults.

## Day-0 Scaffold Checklist
- Create canonical package structure from `13-project-structure-blueprint.md`.
- Add core interface files (runtime, tool runtime, policy middleware, handoff router).
- Add baseline config and environment templates.
- Add initial test directories and CI skeleton.
- Add observability baseline (structured logger + correlation ID helper).

## Minimum Initial Files
- `src/core/orchestrator.py`
- `src/runtime/runtime_adapter.py`
- `src/tools/registry.py`
- `src/policies/middleware.py`
- `src/observability/logging.py`
- `tests/unit/`
- `tests/integration/`
- `.github/workflows/ci.yml`
- `README.md`

## Bootstrap Script Outline
Use a simple script to enforce consistency:
1. create directory tree
2. create placeholder interface modules
3. create test scaffolding
4. create CI stub
5. validate tree against blueprint

## Bootstrap Validation Gates
- structure check passes against expected directories/files
- import smoke test passes
- lint/type check baseline passes
- first unit test executes successfully

## Anti-Patterns to Avoid
- embedding provider logic inside core orchestrator
- adding UI/API framework dependencies to core module
- skipping contracts and implementing adapters ad hoc
- creating plugins without lifecycle and policy hooks

## Related Docs
- `12-bootstrap-checklist.md`
- `13-project-structure-blueprint.md`
- `17-enterprise-cicd-governance.md`
- `20-implementation-coding-standards.md`

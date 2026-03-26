# Docs and Notebooks Cleanup Plan

> **Archived.** Canonical replacement: `docs/plans/notebook-standards.md`, `notebooks/README.md`, `docs/plans/docs-inventory-master.md`. Archived on: 2026-03-25.

## Goal

Create one canonical idea-validation notebook (Notebook 3 style) and a clean notebook suite for module-level validation, while aligning documentation with current Option C API-first architecture.

## Scope

- Documentation cleanup and consolidation (remove stale/redundant guidance, keep one canonical source per topic).
- Notebook consolidation:
  - `01_idea_validation.ipynb` (single canonical end-to-end proof flow).
  - module-focused notebooks for targeted testing and onboarding.
- Verification that notebook flows and docs match real code behavior.

## Constraints

- Do not change architecture contracts during cleanup.
- Keep deterministic-first and provider-neutral boundaries intact.
- Prefer incremental reversible changes.
- Keep existing working notebook logic reusable where possible.

## Slice A - Audit and Inventory

### Tasks

- Inventory all current notebooks under `notebooks/` and map each to:
  - purpose,
  - overlap with other notebooks,
  - stale sections (if any),
  - runtime requirements (`OPENAI_API_KEY`, local-only, etc.).
- Inventory doc pages that reference old notebook flows or outdated workflow assumptions.
- Produce a keep/merge/remove table.

### Deliverables

- `docs/archive/plans/notebooks-inventory.md` (archived)
- `docs/archive/plans/docs-inventory.md` (archived)

### Acceptance

- Every existing notebook is classified as `keep`, `merge`, or `retire`.
- Every impacted doc page is listed with required update action.

## Slice B - Canonical Notebook Design

### Tasks

- Define the canonical "idea test" notebook contract:
  - single workflow run,
  - explicit tool-call interception proof,
  - deterministic execution explanation,
  - clear expected outputs.
- Define module notebook template:
  - purpose,
  - prerequisites,
  - run cell,
  - assertions/check cells,
  - failure troubleshooting cell.

### Deliverables

- `docs/plans/notebook-standards.md`
- target notebook list and ownership map.

### Acceptance

- Clear standard for naming, structure, and validation sections.
- No ambiguity on which notebook is canonical for idea validation.

## Slice C - Notebook Implementation

### Tasks

- Build/reshape notebooks into:
  - `notebooks/01_idea_validation.ipynb` (from current Notebook 3 logic).
  - module notebooks (examples):
    - `notebooks/10_core_orchestrator_checks.ipynb`
    - `notebooks/11_policy_middleware_checks.ipynb`
    - `notebooks/12_runtime_adapter_checks.ipynb`
    - `notebooks/13_tenant_and_limits_checks.ipynb`
- Ensure each notebook has explicit prerequisites and expected outputs.
- Keep API-key-required cells clearly marked.

### Deliverables

- Updated `notebooks/*.ipynb`
- Optional update to `notebooks/build_notebooks.py` if generator remains source of truth.

### Acceptance

- Canonical notebook runs with one interaction workflow and demonstrates deterministic loop clearly.
- Module notebooks each validate one subsystem without cross-purpose confusion.

## Slice D - Documentation Alignment

### Tasks

- Update docs to reference the new canonical notebook set:
  - `README.md`
  - operation guides referencing notebooks
  - relevant plan/tracker docs
- Remove references to retired notebook artifacts.
- Add a quick "which notebook to run for what" table.

### Deliverables

- Updated docs with canonical notebook references.

### Acceptance

- No contradictory notebook guidance across docs.
- A new contributor can pick the correct notebook for each validation goal.

## Slice E - Verification and Evidence

### Tasks

- Execute notebook smoke checks:
  - canonical notebook run,
  - at least one module notebook from each module family.
- Run mandatory quality gates:
  - `python -m pytest -q`
  - `python scripts/architecture/validate_layers.py`
  - `python scripts/architecture/scan_forbidden_imports.py`
- Capture notebook execution evidence in a small report.

### Deliverables

- `artifacts/evidence/notebook-cleanup-validation.md`

### Acceptance

- Notebook suite executes as documented.
- Core gates remain green.

## Rollback Strategy

- Preserve prior notebooks until new canonical suite passes.
- If any module notebook fails or confuses scope, revert only that notebook slice, not the whole suite.
- Keep previous notebook references in git history for traceability.

## Definition of Done

- One canonical idea-validation notebook exists and is easy to run.
- Module notebooks cover key subsystems with focused checks.
- Docs point to the right notebooks and contain no stale references.
- Validation evidence is captured and reproducible.

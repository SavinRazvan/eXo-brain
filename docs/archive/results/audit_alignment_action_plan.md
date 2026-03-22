<!--
File: audit_alignment_action_plan.md
Path: docs/archive/results/audit_alignment_action_plan.md
Role: Actionable remediation plan derived from alignment audit findings.
Used By:
 - .agents/skills/review-pr/SKILL.md
 - .agents/skills/prepare-pr/SKILL.md
 - .agents/skills/merge-pr/SKILL.md
Depends On:
 - docs/archive/results/audit_alignment_results.md
 - .local/workflow-artifacts/alignment/alignment-audit.md
 - .local/workflow-artifacts/alignment/alignment-todos.md
Notes:
 - This plan is execution-oriented and must stay aligned with advisory audit outputs.
-->

# Audit Alignment Action Plan

> Status: archived
> Canonical replacement: `.local/workflow-artifacts/alignment/alignment-todos.md`
> Archived on: 2026-03-19
> Archive reason: historical snapshot

## Metadata
- Date: 2026-03-01
- Source decisions: `refresh-baseline-v2`
- Policy posture:
  - No active P0 in current revalidated baseline
  - Deterministic policy-gated execution remains mandatory for state-changing/high-impact operations
  - Strict priority-map validation (`ValueError` on unknown roles)
  - Precedence: `rules/AGENTS` > roadmap > research > historical notes
  - Small PR slices (1-2 findings per PR)
  - Finding closure tied to PR + evidence links
  - Accepted divergences tracked with expiry/review date

## Execution Order (Approved)
1. Slice 0: Results rebaseline and stale-claim closure
2. Slice 1: Enterprise module completeness (`finops`, `model_governance`) decision/implementation
3. Slice 2: CI security gate alignment (`security_scan` expectation)
4. Slice 3: PR phase skill attribution contract hardening
5. Slice 4: Structure/traceability/documentation cleanup

## Global Constraints
- No monolith changes: each PR addresses 1-2 findings maximum.
- Maintain provider-neutral boundaries and deterministic tool safety.
- Required gates per slice:
  - `python -m pytest -q`
  - `python scripts/architecture/validate_layers.py`
  - `python scripts/architecture/scan_forbidden_imports.py`
  - branch/PR linkage checks from `.cursor/rules/pr-workflow-enforcement.mdc` before merge:
    - `python scripts/pr/verify_publish.py --branch <current-branch>`
    - `gh pr view --json headRefName,url,state`
    - `git ls-remote --heads origin <branch>`
- Required artifacts:
  - `.local/workflow-artifacts/pr/review.md`
  - `.local/workflow-artifacts/pr/prep.md`
  - `.local/workflow-artifacts/pr/merge.md`
  - `.local/workflow-artifacts/alignment/alignment-audit.md` and `.local/workflow-artifacts/alignment/alignment-todos.md` for architecture-impacting slices

---

## Slice 0 - Results Rebaseline (Completed)

### Scope
- Revalidate previously highest-severity findings against current code/tests.
- Remove stale severity inflation from results artifacts.
- Realign remediation order with current evidence.

### Target Areas
- `docs/archive/results/audit_alignment_results.md`
- `docs/archive/results/audit_alignment_action_plan.md`
- `.local/workflow-artifacts/alignment/alignment-audit.md`
- `.local/workflow-artifacts/alignment/alignment-todos.md`

### Tasks
1. Revalidate stale P0/P1 claims with direct source + test evidence.
2. Update results totals and module-group highlights.
3. Update action sequencing to reflect current open findings.
4. Record closed/reclassified findings in lifecycle tracking artifacts.

### Acceptance
- Prior stale P0 persistence claim removed from active queue.
- Results/action-plan/docs-local artifacts are internally consistent.

### Rollback/Fallback
- Keep prior snapshot in git history for auditability.

---

## Slice 1 - Enterprise Module Completeness (`finops`, `model_governance`)

### Scope
- Resolve missing P1 modules declared in enterprise-readiness docs.
- Choose implement-now or explicit defer-with-owner/due-slice for each module.

### Target Areas
- `src/finops/*`
- `src/model_governance/*`
- `tests/modules/finops/*`
- `tests/modules/model_governance/*`
- related roadmap/research ownership docs

### Tasks
1. Confirm ownership and due-slice decision for each missing module.
2. If implementing: add provider-neutral contracts + minimal tested vertical slice.
3. If deferring: add explicit defer rationale, owner, due-slice, and review date in authoritative docs.
4. Update traceability links roadmap -> code/tests.

### Test Matrix
- Implementation path:
  - module tests under `tests/modules/<module>/` pass.
  - required global gates pass.
- Defer path:
  - documentation validation confirms explicit owner + due-slice + review cadence.

### Acceptance
- `AA-trace-001` and `AA-trace-002` are closed or accepted-divergence with explicit metadata.

### Rollback/Fallback
- Feature-flag new module integrations until full policy and observability coverage is complete.

---

## Slice 2 - CI Security Gate Alignment

### Scope
- Reconcile `security_scan` expectation with actual architecture-fitness workflow enforcement.

### Target Areas
- `.github/workflows/architecture-fitness.yml`
- `docs/archive/plans/backlog-reconciliation-v4-execution-board.md`

### Tasks
1. Decide security scanning baseline (secrets/dependencies/license).
2. Add explicit workflow gate(s) or document accepted divergence with rationale and timebox.
3. Ensure gate outcome is visible in PR checks.

### Test Matrix
- Workflow dry-run (where applicable) + PR check visibility verification.
- Global required gates remain green.

### Acceptance
- `AA-trace-003` closed with explicit CI evidence or accepted divergence record.

### Rollback/Fallback
- Keep checklist note as conditional until workflow gate is promoted.

---

## Slice 3 - PR Attribution Contract Hardening

### Scope
- Make rule-mandated attribution fields explicit in each phase skill contract.

### Target Areas
- `.agents/skills/review-pr/SKILL.md`
- `.agents/skills/prepare-pr/SKILL.md`
- `.agents/skills/merge-pr/SKILL.md`
- `.cursor/rules/pr-action-attribution.mdc`

### Tasks
1. Add explicit required attribution block for each phase artifact.
2. Ensure each skill names its phase label requirement (`Reviewed-By`, `Prepared-By`, `Merged-By`).
3. Keep script-based generation as implementation detail, not sole implicit guarantee.

### Test Matrix
- Skill/rule consistency check across all PR workflow docs.
- Manual dry-run artifact generation check in one sample PR.

### Acceptance
- `AA-policy-002`, `AA-policy-003`, and `AA-policy-004` are closed.

### Rollback/Fallback
- Keep prior wording in history if maintainers require transition guidance.

---

## Slice 4 - Structure/Traceability/Docs Cleanup

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
2. Add canonical module inventory in `docs/architecture/mvp.md`.
3. Align docs with active module/test layout and enforced gates.
4. Rehome `tests/modules/unknown` governance tests to a stable domain bucket (or document accepted convention).
5. Normalize malformed rule frontmatter where required.
6. Add or refresh accepted divergence entries with owner + expiry/review date.
7. Ensure PR workflow docs reference alignment audit artifacts where required.

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

For each finding tracked in `.local/workflow-artifacts/alignment/alignment-todos.md`, maintain:
- `status`: `open | in_progress | fixed | deferred | accepted`
- `owner`: GitHub username
- `slice`: remediation slice ID
- `pr_link`: pull request URL
- `evidence_link`: artifact reference (`.local/workflow-artifacts/pr/review.md`, `.local/workflow-artifacts/pr/prep.md`, test output)
- `last_updated`: date
- `review_due` (required for `accepted` divergences)

## Initial Finding-to-Slice Mapping
- Slice 0:
  - stale baseline cleanup (`AA-docs-001`) [completed]
- Slice 1:
  - enterprise module gaps (`AA-trace-001`, `AA-trace-002`)
- Slice 2:
  - CI security gate drift (`AA-trace-003`)
- Slice 3:
  - phase artifact attribution gaps (`AA-policy-002`, `AA-policy-003`, `AA-policy-004`)
- Slice 4:
  - structural and documentation drift (`AA-structure-*`, `AA-trace-004`, `AA-trace-005`, `AA-policy-005`)

## Definition of Done (Plan-Level)
- P0 findings: zero open.
- P1 findings: either fixed or explicitly accepted with expiry and owner.
- All slices completed through PR workflow with green required gates.
- Alignment artifacts updated and internally consistent.

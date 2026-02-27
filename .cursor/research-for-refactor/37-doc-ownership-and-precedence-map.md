# Doc Ownership and Precedence Map

## Goal
Prevent contradiction and duplicate ownership across research docs by defining single-source-of-truth precedence.

## Precedence Rule
When two docs appear to overlap, resolve by this order:
1. **Contracts and schemas**
2. **Quality/security/release gates**
3. **Implementation sequence and scaffolding**
4. **Examples and explanatory guidance**

## Source-of-Truth Map

## Contracts and Runtime Behavior (Highest Priority)
- Runtime/tool/policy schemas and mode rules:
  - `31-tool-calling-contracts-and-mode-selection.md`
- Provider capability contract and matrix:
  - `10-provider-capability-matrix.md`
- Provider settings and registry contract:
  - `34-provider-registry-and-settings-schema.md`
- Architecture interfaces and package boundaries:
  - `02-target-architecture.md`
  - `08-module-requirements-matrix.md`

## Release and Governance Gates
- Milestone done criteria:
  - `09-definition-of-done-and-quality-gates.md`
- Enterprise quality thresholds:
  - `15-enterprise-quality-gates.md`
- Security baseline controls:
  - `19-enterprise-security-baseline-controls.md`
- CI/CD governance:
  - `17-enterprise-cicd-governance.md`
- Architecture fitness CI checklist:
  - `35-architecture-fitness-ci-checklist.md`

## Implementation and Delivery Planning
- MVP implementation order:
  - `06-mvp-build-sequence.md`
- Bootstrap and scaffold:
  - `12-bootstrap-checklist.md`
  - `24-repo-bootstrap-scaffold.md`
- Migration and reuse plan:
  - `04-phased-migration-plan.md`
  - `11-port-matrix.md`

## Examples and Supporting Guides (Non-Authoritative)
- Mode-selection examples:
  - `33-mode-selection-policy-examples.md`
- PR/release evidence template:
  - `23-pr-release-evidence-templates.md`
- Interface template:
  - `22-interface-contract-template.md`
- GitHub Actions skeleton:
  - `36-github-actions-architecture-fitness-skeleton.md`

## Anti-Contradiction Maintenance Rules
- If enum values change (for example `provider_native`), update contract docs first (`31`, `10`, `34`) then propagate.
- If adapter method signatures change, update `02`, `10`, `31`, then update checklists/tests/docs.
- Examples (`33`, `36`) must never define new behavior that conflicts with contracts.
- Evidence templates (`23`) mirror gate docs (`09`, `15`, `19`, `35`) and should not add independent requirements.

## Review Cadence
- Run cross-doc consistency review at:
  - milestone completion
  - before release candidate cut
  - after any contract schema version bump

## Related Docs
- `README.md`
- `31-tool-calling-contracts-and-mode-selection.md`
- `35-architecture-fitness-ci-checklist.md`

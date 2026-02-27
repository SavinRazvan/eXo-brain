# PR and Release Evidence Templates

## Goal
Enforce consistent quality/security evidence for implementation PRs and release candidates.

## Pull Request Template (Essential)

## Summary
- Problem:
- Proposed change:
- Module(s) affected:

## Risk and Safety
- Risk tier (`low`/`medium`/`high`):
- Side-effecting operations changed:
- Rollback plan:

## Validation
- Unit tests:
- Integration tests:
- Failure-path tests:
- Replay/chaos tests (if applicable):

## Observability
- Logs/traces/metrics updated:
- Correlation fields validated:

## Security and Policy
- Auth/policy implications:
- Tenant isolation impact:
- Secret or credential impact:

## Evidence Links
- CI run:
- Test report:
- Gate results:
- Architecture fitness CI report:
- Adapter conformance checklist:
- Workflow parity report:
- Mode-selection decision trace sample:
- Provider registry/settings validation report:

## Release Candidate Evidence Template

## Release Metadata
- Release ID:
- Source revision:
- Artifact digest/signature:

## Gate Status
- P0 security gates:
- P0 quality/reliability gates:
- Open risks/exceptions:

## Performance and Reliability
- SLO snapshot:
- Canary result:
- Rollback verification status:
- Adapter latency/cost benchmark snapshot:

## Compliance and Audit
- Audit integrity check:
- Evidence bundle storage location:

## Go/No-Go Decision
- Decision:
- Approvers:
- Notes:

## Related Docs
- `15-enterprise-quality-gates.md`
- `16-enterprise-testing-strategy.md`
- `17-enterprise-cicd-governance.md`
- `19-enterprise-security-baseline-controls.md`
- `32-adapter-conformance-checklist.md`
- `33-mode-selection-policy-examples.md`
- `34-provider-registry-and-settings-schema.md`
- `35-architecture-fitness-ci-checklist.md`

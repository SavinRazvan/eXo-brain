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

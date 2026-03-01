# Module Hardening Slice Checklist

Use this checklist in each module-hardening PR to keep execution consistent and auditable.

## Slice Header
- Slice name:
- Module group:
- Branch:
- Rollback strategy:
- Fallback behavior:

## A) Contract + Validation
- [ ] Inputs validated at module boundary
- [ ] Output/error envelope contract confirmed
- [ ] Policy pre-checks and post-checks applied where needed

## B) Logging + Observability
- [ ] Correlation IDs propagated (`job/task/agent/tool`)
- [ ] Structured logs for key decisions (allow/deny/escalate/retry/fallback)
- [ ] Tenant/identity context included where applicable
- [ ] Secret redaction expectations preserved

## C) Error Handling
- [ ] Typed errors for expected failure classes
- [ ] Deterministic fallback/blocked envelope for controlled failures
- [ ] No silent catch-and-ignore paths
- [ ] Retryability is explicit for transient failures

## D) Testing
- [ ] Unit tests: happy path
- [ ] Unit tests: failure path
- [ ] Unit tests: edge/malformed input path
- [ ] Integration tests updated for touched module boundaries
- [ ] Replay/retry tests added when behavior is stateful or high-impact

## E) Gates
- [ ] `pytest -q` passes
- [ ] `python scripts/architecture/validate_layers.py` passes
- [ ] `python scripts/architecture/scan_forbidden_imports.py` passes
- [ ] Relevant module subset tests pass

## F) Evidence + Docs
- [ ] `.local/review.md` updated with findings and recommendation
- [ ] `.local/prep.md` updated with gate evidence
- [ ] `.local/merge.md` updated in merge phase with merge evidence and follow-ups
- [ ] Docs updated for changed contracts/behaviors
- [ ] CI workflow paths verified if tests/scripts moved

## G) Release Readiness Decision
- [ ] READY for merge
- [ ] NEEDS WORK (list blockers)
- [ ] NEEDS DISCUSSION (list open decisions)

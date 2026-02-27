# Execution Workflow and Handoffs

## Goal
Standardize how work moves from planning to delivery so agents and humans execute efficiently with minimal rework.

## Standard Workflow
1. **Scope**: define module, objective, acceptance criteria.
2. **Design**: confirm interfaces, events, policy implications.
3. **Implement**: smallest shippable increment only.
4. **Validate**: tests + failure-path checks + observability verification.
5. **Evidence**: attach logs, metrics, and gate status.
6. **Document**: update relevant research/docs and decision records.

## Handoff Contract (Required)
Each handoff must include:
- task summary
- changed module(s)
- interface changes (if any)
- risk and rollback notes
- test status and missing coverage
- next recommended action

## Agent Role Split
- Architecture Researcher: boundaries, interfaces, risk analysis.
- Tooling Strategist: tool runtime, policy gates, MCP/decorators.
- Migration Architect: milestones, rollout, rollback, validation gates.

## Stop Conditions
Pause and escalate when:
- interface contract is unclear
- cross-module coupling increases unexpectedly
- security or tenant-isolation behavior is uncertain
- gate evidence is missing for a production-impacting change

## Related Docs
- `07-agent-orchestration-plan.md`
- `09-definition-of-done-and-quality-gates.md`
- `17-enterprise-cicd-governance.md`

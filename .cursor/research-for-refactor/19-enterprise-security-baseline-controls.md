# Enterprise Security Baseline Controls

## Goal
Define the essential minimum security controls required before production onboarding so the framework remains safe, auditable, and tenant-isolated.

## Scope
This is a baseline, not a full certification framework.  
It covers only mandatory controls for:
- identity and access
- tenant isolation
- secrets and key lifecycle
- secure tool/plugin execution
- supply-chain and deployment security
- logging, audit, and incident response readiness

## Control Priority Model
- `P0` (must have before prod)
- `P1` (must have before scale expansion)
- `P2` (hardening/optimization)

## Security Baseline Matrix

| Control ID | Control Area | Priority | Requirement | Verification | Owner |
|---|---|---|---|---|---|
| SEC-01 | AuthN | P0 | Strong service and user authentication with short-lived tokens where possible | integration tests + config review | Platform |
| SEC-02 | AuthZ | P0 | RBAC/policy-based authorization for tools, workflows, and admin operations | policy regression tests | Security/Platform |
| SEC-03 | Tenant Isolation | P0 | Hard isolation boundaries for sessions, checkpoints, logs, and storage | cross-tenant attack tests | Platform |
| SEC-04 | Secrets | P0 | Secrets stored in manager/KMS only; no plaintext in code/logs/artifacts | secret scan + runtime checks | Security |
| SEC-05 | Key Rotation | P0 | Credential/key rotation procedure with no prolonged downtime | rotation drill evidence | Security/SRE |
| SEC-06 | Audit Trail | P0 | Tamper-evident audit records for security and policy decisions | audit verifier job | Security |
| SEC-07 | Data Redaction | P0 | Sensitive data redacted in logs/traces/exports | redaction tests + log inspection | Security |
| SEC-08 | Tool Safety | P0 | High-risk tool calls gated by policy and approval paths | scenario tests | Platform |
| SEC-09 | Plugin Integrity | P1 | Plugin load path restricted; plugin signature/hash verification | plugin validation tests | Platform |
| SEC-10 | Dependency Security | P0 | CI vulnerability scanning and policy on critical CVEs | CI gate report | DevSecOps |
| SEC-11 | SBOM + Provenance | P1 | Signed artifacts with SBOM/provenance for releases | release evidence bundle | DevSecOps |
| SEC-12 | Runtime Egress Policy | P1 | Controlled outbound network policies for adapters/plugins | policy tests + runtime audit | Platform/SRE |
| SEC-13 | Rate Limiting | P1 | Abuse protection on critical APIs/workflows/tool invocations | load and abuse tests | Platform |
| SEC-14 | Session Security | P1 | Session integrity controls and anti-replay protections for privileged actions | replay/abuse test suite | Security |
| SEC-15 | Incident Readiness | P0 | Breach response + on-call runbooks exercised | drill report | SRE/Security |
| SEC-16 | Backup/Recovery Security | P1 | Encrypted backups with access controls and restore verification | recovery drill + audit | SRE |

## Mandatory P0 Controls (Go-Live Minimum)
Production go-live is blocked unless all controls below are satisfied:
- `SEC-01` AuthN
- `SEC-02` AuthZ
- `SEC-03` Tenant Isolation
- `SEC-04` Secrets
- `SEC-05` Key Rotation
- `SEC-06` Audit Trail
- `SEC-07` Data Redaction
- `SEC-08` Tool Safety
- `SEC-10` Dependency Security
- `SEC-15` Incident Readiness

## Baseline Technical Guardrails

## Identity and Access
- deny-by-default authorization model
- least-privilege roles for operators, services, and plugin runtime
- separate break-glass access with strict audit logging

## Secrets and Cryptography
- all secrets loaded at runtime from secret manager
- encryption in transit and at rest for sensitive stores
- key rotation cadence documented and tested

## Runtime and Tooling Safety
- side-effecting tools require policy gate decision logging
- plugin registration restricted to approved allowlist
- MCP/custom integrations classified by trust tier

## Supply Chain and CI/CD
- signed release artifacts only
- vulnerability and license scan gates in CI
- release blocked on critical unapproved vulnerabilities

## Observability and Forensics
- structured logs with correlation IDs
- immutable audit trail for security-relevant actions
- retention policy for incident investigation windows

## Verification Cadence
- per PR: secret scan + dependency scan + policy lint
- per release candidate: security integration + abuse-path scenarios
- monthly: key rotation drill + incident response exercise
- quarterly: tenant isolation stress test + control review

## Minimal Evidence Pack (Security)
Every production release should include:
- security gate report (pass/fail per control)
- dependency and secret scan outputs
- audit integrity verification result
- key rotation drill date + outcome
- latest incident drill report reference

## Exceptions Policy
- exceptions require documented risk acceptance
- exception must include expiration date and compensating controls
- no exceptions allowed for unresolved `P0` controls in production go-live

## Exit Criteria (Security Baseline Complete)
- all `P0` controls implemented and verified
- no open critical security findings without approved mitigation
- evidence pack complete and attached to release record
- operational runbooks validated with at least one drill cycle

## Related Docs
- `14-enterprise-readiness-modules.md`
- `15-enterprise-quality-gates.md`
- `17-enterprise-cicd-governance.md`
- `18-enterprise-operational-runbooks.md`

# Versioning and Release Roadmap

## Goal
Define a clear versioning model and phased release roadmap so the project evolves safely from foundation to enterprise scale.

## Versioning Model

Use semantic versioning:
- `MAJOR.MINOR.PATCH`
- `MAJOR`: breaking contract or architecture changes
- `MINOR`: backward-compatible features
- `PATCH`: backward-compatible fixes/hardening

Rule:
- no breaking interface changes in `v1.x` without explicit deprecation window.

## Release Channels
- `alpha`: internal architecture validation and experiments
- `beta`: early adopters with controlled risk
- `stable`: production-ready releases with full gate evidence

## Roadmap

## V1.0.0 (Foundation Release)
Scope:
- core orchestration boundaries
- runtime mode selector (`openai_native` + deterministic)
- first runtime adapters (OpenAI + OpenAI-compatible)
- deterministic tool runtime + policy middleware
- persistence module baseline (`sqlite` + `postgres`)
- MCP baseline integration
- observability baseline (logs/timeline/metrics/traces)

Required gates:
- `15-enterprise-quality-gates.md` P0 set (adapted for initial production profile)
- `16-enterprise-testing-strategy.md` baseline tracks
- `19-enterprise-security-baseline-controls.md` mandatory P0 controls

Exit criteria:
- vertical slice fully operational and repeatable
- no unresolved P0 security/reliability issues

## V1.1 to V1.3 (Stabilization and Hardening)
Scope:
- performance and reliability hardening
- profile parity improvements (`managed_cloud` vs `self_hosted`)
- expanded integration/replay/resilience coverage
- stronger CI/CD evidence automation and rollback readiness

Exit criteria:
- stable release cadence
- reduced failure rate and improved MTTR trend
- parity tests passing across deployment profiles

## V2.0.0 (Scale and Enterprise Expansion)
Scope:
- advanced multi-tenancy controls and governance depth
- expanded policy engine capabilities
- advanced finops/model governance workflows
- broader adapter ecosystem and operational automation

Breaking-change policy:
- publish migration guide before `v2.0.0`
- maintain temporary compatibility shims where feasible

Exit criteria:
- enterprise readiness modules materially complete
- documented migration path from latest `v1.x`

## Deprecation Policy
- mark deprecated interfaces in one `MINOR` release
- provide at least one release-cycle migration window
- remove deprecated interfaces only in next `MAJOR` release

## Release Governance
- every stable release requires:
  - evidence bundle
  - gate summary
  - rollback validation
  - release notes with risk classification

- hotfix (`PATCH`) releases allowed only for critical defects/security issues.

## Suggested Milestone Cadence
- `v1.0.0-alpha`: architecture + contracts + first vertical slice
- `v1.0.0-beta`: broader test coverage + profile checks
- `v1.0.0`: stable foundation
- `v1.1+`: iterative hardening and expansion
- `v2.0.0`: major enterprise expansion and intentional breaking improvements

## Related Docs
- `12-bootstrap-checklist.md`
- `15-enterprise-quality-gates.md`
- `16-enterprise-testing-strategy.md`
- `17-enterprise-cicd-governance.md`
- `27-reference-tech-stack-lock-v1.md`

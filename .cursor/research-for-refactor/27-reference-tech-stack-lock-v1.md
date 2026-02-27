# Reference Tech Stack Lock V1

## Goal
Lock a practical V1 technology stack for implementation so teams can execute without repeated stack churn.

## Lock Scope
This lock applies to:
- core framework implementation
- runtime adapters
- background execution
- storage, observability, security baseline
- CI/CD and release evidence flow

This lock does not prevent adding optional adapters/plugins later.

## V1 Selected Stack (Locked)

## Language and Build
- Python `3.12+`
- Packaging/dependency workflow: `uv` + `pyproject.toml`
- Test runner baseline: `pytest`

## Core Runtime and Integration
- Orchestration core: custom module in Python
- Optional host integration (not core requirement): `FastAPI` adapter
- Background jobs: `Celery` (primary)
- Event style: internal EDA + external queue for distributed execution

## Data and State
- Durable state: PostgreSQL
- Queue/cache/rate-limit: Redis (or Valkey-compatible deployment)
- Artifacts/evidence: S3-compatible object storage

## Observability
- OpenTelemetry instrumentation
- Prometheus-compatible metrics
- Loki/ELK-compatible structured logs
- Jaeger/Tempo-compatible tracing backend

## Security and Governance
- Secrets provider abstraction with Vault/KMS-compatible implementations
- Policy middleware in core, adapter-ready for external policy engines
- Signed artifacts and provenance required in CI/CD release flow

## LLM Runtime Adapters
- OpenAI Agents SDK adapter (first-class)
- OpenAI-compatible adapter (vLLM/TGI/Ollama style endpoints)
- Custom provider adapter contract

## MCP
- MCP client abstraction supporting stdio/http transports
- trust-tier enforcement in policy layer

## V1 Not Selected (Explicitly Deferred)
- TypeScript/Node as primary runtime
- Kafka/NATS as mandatory baseline message bus
- Service mesh as hard requirement for MVP
- Multi-region active-active as V1 requirement
- Heavy workflow engines as mandatory core dependency

## Version Policy
- Use latest stable versions at bootstrap unless blocked by compatibility.
- Pin exact versions in lockfiles for reproducible builds.
- Update cadence:
  - patch updates: continuous
  - minor updates: scheduled (monthly/bi-monthly)
  - major updates: gated by compatibility and replay tests

## Change Control for Stack Lock
Any stack-lock change requires:
1. documented rationale and alternatives considered
2. impact assessment on portability, security, and operability
3. passing quality/security/reliability gates
4. update of this lock document + profile matrix

## Review Cadence
- Formal review every 6 weeks during active build phase.
- Emergency review allowed for security/CVE-driven updates.

## Acceptance Criteria
- all implementation teams use this stack lock as default
- no ad hoc infrastructure dependency introduced without review
- CI checks and deployment profiles align with lock decisions

## Related Docs
- `25-technology-stack-decisions.md`
- `26-deployment-profiles-matrix.md`
- `17-enterprise-cicd-governance.md`
- `19-enterprise-security-baseline-controls.md`

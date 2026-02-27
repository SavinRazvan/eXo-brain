# Technology Stack Decisions (Redacted)

## Goal
Define a concrete, cloud-agnostic technology stack for the new Python-based framework with hybrid managed/self-hosted operation.

## Phase 1 Baseline Stack
- **Language/runtime**: Python 3.12+.
- **Packaging**: `uv` + `pyproject.toml`.
- **Optional host adapter API**: `FastAPI` (core remains transport-agnostic).
- **Background runtime**: `Celery` (or `Arq` if async-first simplicity is preferred).
- **Messaging**: internal in-process EDA + external queue for distributed background work.
- **Data stores**:
  - Postgres for durable state.
  - Redis for queue/cache/rate limiting.
  - S3-compatible object storage abstraction for artifacts/evidence.
  - Persistence module with adapter-based stores (`postgres` for production profiles, `sqlite` for local/dev profile).
- **Observability**:
  - OpenTelemetry for traces/metrics/log correlation.
  - Prometheus-compatible metrics.
  - Loki/ELK-compatible structured logging.
  - Jaeger/Tempo-compatible tracing backend.
- **Security**:
  - Vault/KMS abstraction for secrets.
  - Pluggable policy boundary (start internal, keep adapter-ready for OPA/Cedar style).
  - CI/CD artifact signing boundary (Sigstore/Cosign style).
- **Runtime adapters**:
  - OpenAI Agents SDK adapter.
  - OpenAI-compatible adapter (vLLM/TGI/Ollama style endpoints).
  - Custom adapter contract for future providers.
- **MCP**: stdio/http MCP client abstraction with trust-tier policy enforcement.

## Cloud-Agnostic Hybrid Mapping
- Keep critical services behind provider-neutral interfaces in `runtime/`, `persistence/`, `storage/`, `observability/`, and `security/`.
- Maintain two deploy profiles per service:
  - managed cloud profile
  - self-hosted/on-prem profile
- Ensure profile parity through environment-driven configuration and shared capability maps.

## Decision Rules
- Prefer portability first, provider lock-in second.
- Keep orchestration core independent of cloud/provider-specific SDK internals.
- Use managed services in cloud where they improve delivery speed, with equivalent self-hosted options for on-prem.
- Do not finalize stack details until vertical-slice evidence passes quality and security gates.

## Validation Before Lock-In
Build a vertical slice that validates:
- one runtime adapter path
- deterministic tool runtime with policy middleware
- background queue execution
- trace/log correlation end-to-end

Validate against:
- `15-enterprise-quality-gates.md`
- `16-enterprise-testing-strategy.md`
- `17-enterprise-cicd-governance.md`
- `19-enterprise-security-baseline-controls.md`

## Sequencing
1. Finalize stack and deployment profile decisions.
2. Freeze storage/queue/observability/security adapter contracts.
3. Build and measure vertical slice.
4. Adjust choices only where evidence shows risk or portability gaps.
5. Proceed to full bootstrap implementation.

## Related Docs
- `02-target-architecture.md`
- `10-provider-capability-matrix.md`
- `12-bootstrap-checklist.md`
- `24-repo-bootstrap-scaffold.md`

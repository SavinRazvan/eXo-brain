# Deployment Profiles Matrix (Managed vs Self-Hosted)

## Goal
Define equivalent deployment profiles for cloud-managed and on-prem/self-hosted operation while preserving the same architecture contracts.

## Profile Model
- `managed_cloud`: preferred for delivery speed and reduced ops burden.
- `self_hosted`: preferred for strict enterprise/on-prem environments.
- `hybrid`: support both profiles with identical interfaces and behavior expectations.

## Core Service Matrix

| Capability | Interface Boundary | Managed Cloud Profile | Self-Hosted Profile | Portability Notes |
|---|---|---|---|---|
| Durable state (sessions/checkpoints/metadata) | `storage/state_store.py` | Managed Postgres service | PostgreSQL (HA) | Same schema migrations and transaction semantics required |
| Queue + cache + rate limiting | `runtime/queue_adapter.py` | Managed Redis service | Redis/Valkey cluster | Keep retry/backoff semantics identical across profiles |
| Artifact/evidence storage | `storage/object_store.py` | Managed object storage (S3-compatible) | MinIO or S3-compatible object store | Use S3 API abstraction only; avoid provider-only SDK paths in core |
| Secret management | `security/secrets_provider.py` | Cloud secret manager/KMS | Vault + local HSM/KMS equivalent | Keep secret access API stable; rotation hooks mandatory |
| Metrics backend | `observability/metrics_sink.py` | Managed Prometheus-compatible service | Prometheus stack | Standardize metric names and labels |
| Log backend | `observability/log_sink.py` | Managed log platform | Loki or ELK stack | Enforce JSON structured logs and field parity |
| Trace backend | `observability/trace_sink.py` | Managed tracing/APM backend | Jaeger/Tempo | OpenTelemetry exporter abstraction required |
| Policy decision engine | `policies/engine_adapter.py` | Managed policy service (optional) | Embedded policy engine + optional OPA | Keep allow/deny/escalate decision envelope fixed |
| CI artifact registry | `release/artifact_registry.py` | Managed container/artifact registry | Self-hosted registry | Enforce signing and provenance in both modes |
| Runtime compute | `integration/host_adapter.py` + deployment manifest | Managed Kubernetes/container platform | Kubernetes/OpenShift/VM orchestration | Keep deployment config profile-driven, not code-driven |

## Runtime Adapter Matrix

| Adapter Type | Managed Cloud Profile | Self-Hosted Profile | Required Contract Guarantees |
|---|---|---|---|
| OpenAI Agents runtime | OpenAI/Azure-hosted endpoints | Through outbound enterprise network policy | Session lifecycle, tool-call callbacks, and error envelopes identical |
| OpenAI-compatible runtime | Managed compatible endpoints | vLLM/TGI/Ollama private endpoints | Capability map must gate unsupported features safely |
| Custom runtime | Provider-specific managed APIs | In-house/self-hosted inference runtime | Must implement `RuntimeAdapter` contract fully |

## Network and Security Profile Differences

| Area | Managed Cloud | Self-Hosted | Baseline Requirement |
|---|---|---|---|
| Egress | policy-controlled outbound access | strict enterprise firewall egress allowlist | adapters must honor timeout/retry and egress policy hooks |
| Identity | cloud IAM + workload identities | enterprise IdP + service accounts | least-privilege and auditable authz decisions |
| Certificate/key mgmt | cloud cert/key services | enterprise PKI/HSM flows | rotation and revocation procedures tested |
| Audit retention | managed audit stores | internal SIEM/archive | retention and query parity for incident response |

## Configuration Strategy
- Keep a single configuration schema with profile overlays:
  - `config/profiles/managed_cloud.yaml`
  - `config/profiles/self_hosted.yaml`
  - `config/profiles/hybrid.yaml`
- No profile-specific logic inside orchestration core.
- Profile selection must be environment-driven and observable in startup logs.

### N3 profile defaults (implemented baseline)

`create_app()` now supports `EXO_DEPLOYMENT_PROFILE` with profile-aware defaults:

| Profile | `EXO_TOOL_ARTIFACT_DIRECTORY` default | `EXO_AUDIT_EXPORT_DIRECTORY` default | `EXO_BYOC_STORE_BACKEND` default | `EXO_BYOC_CLEANUP_INTERVAL_SECONDS` default |
|---|---|---|---|---|
| `managed_cloud` | `.exo_data/tool_artifacts/managed_cloud` | `.exo_data/audit_exports/managed_cloud` | `sqlite` | `20` |
| `self_hosted` | `.exo_data/tool_artifacts/self_hosted` | `.exo_data/audit_exports/self_hosted` | `sqlite` | `30` |
| `hybrid` | `.exo_data/tool_artifacts/hybrid` | `.exo_data/audit_exports/hybrid` | `sqlite` | `25` |

Notes:
- Explicit environment variables continue to override profile defaults.
- Existing behavior remains backward compatible when `EXO_DEPLOYMENT_PROFILE` is unset (`managed_cloud`).

### Hosted external beta release evidence links

- Profile-default runtime/config implementation:
  - `src/config/settings.py`
  - `src/api/app.py`
- Regression coverage for profile behavior:
  - `tests/modules/api/test_deployment_profile_defaults.py`
- Operations hardening artifacts:
  - `docs/operations/byoc-artifact-integrity-dashboard.md`
  - `.cursor/research-for-refactor/18-enterprise-operational-runbooks.md`
  - `docs/plans/tenant-tool-execution-architecture.md`

## Validation Matrix (Must Pass for Both Profiles)
- contract tests (adapters, tools, policies, storage)
- deterministic replay tests for high-risk workflows
- resilience tests (queue saturation, provider outages, checkpoint recovery)
- security baseline checks from `19-enterprise-security-baseline-controls.md`
- release and deployment gates from `17-enterprise-cicd-governance.md`

## Rollout Recommendation
1. Start with `managed_cloud` for speed.
2. Build compatibility harness and run weekly parity tests against `self_hosted`.
3. Promote `hybrid` support only after profile parity reaches required quality/security gates.

## Exit Criteria
- all critical capabilities run in both profiles without contract drift
- no unresolved P0 security or reliability gaps per profile
- deployment playbooks and runbooks validated for both profiles

## Related Docs
- `17-enterprise-cicd-governance.md`
- `19-enterprise-security-baseline-controls.md`
- `25-technology-stack-decisions.md`

# Project Status

Last updated: 2026-05-26

## Public Maturity Summary

eXo-brain is a single-maintainer reference implementation. It is useful for
architecture review, local experimentation, and design-partner conversations. It
is not a production enterprise platform or certified compliance product.

## Delivered

| Area | Status | Evidence |
|------|--------|----------|
| FastAPI control plane | Delivered for local evaluation | `src/api/`, `src/api/routers/*` |
| REST/SSE/WebSocket governed turns | Delivered for default API path | `src/api/routers/turns.py`, `docs/architecture/governed-execution-pipeline.md` |
| Deterministic tool executor | Delivered | `src/tools/executor.py` |
| Policy middleware and risk gates | Delivered baseline | `src/policies/*` |
| Ingress gate chain | Delivered baseline with profile/config support | `src/policies/ingress_gates.py`, `src/policies/ingress_profiles.py` |
| Provider-neutral runtime contract | Delivered baseline | `src/runtime/runtime_adapter.py`, `src/runtime/adapter_factory.py` |
| OpenAI-oriented runtime path | Delivered baseline | `src/runtime/openai_agents_runtime.py`, `src/runtime/openai_compatible_runtime.py` |
| Tenant runtime composition | Delivered | `src/runtime/tenant_runtime.py`, `src/tenancy/*` |
| SQLite persistence | Delivered for local and pilot-style evaluation | `src/persistence/adapters/sqlite*.py` |
| BYOC tool runtime primitives | Delivered baseline | `src/tools/byoc/*` |
| MCP tool integration baseline | Delivered baseline | `src/mcp/*` |
| Architecture boundary checks | Delivered | `scripts/architecture/validate_layers.py`, `scripts/architecture/scan_forbidden_imports.py` |
| Public governance files | Delivered | `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `MAINTAINER_STATUS.md` |

## Partial or Planned

| Area | Status | Notes |
|------|--------|-------|
| Production deployment packaging | Partial | `docker-compose.yml` is local-only and explicitly not a production template. No supported Helm/Kubernetes distribution is claimed. |
| Multi-node datastore strategy | Partial | SQLite is the current durable backend. Postgres/HA datastore packaging is not delivered. |
| Human approval lifecycle APIs | Planned | Escalation/reason-code paths exist, but first-class approve/reject lifecycle APIs are not complete. |
| MCP governance depth | Planned | Baseline MCP integration exists; per-server/per-tool allow-deny policy and credential-scope governance need deeper implementation. |
| Standard telemetry certification | Partial | Telemetry hooks exist, but enterprise collector/dashboard certification is not complete. |
| Adapter ecosystem breadth | Partial | OpenAI-oriented paths exist; broader provider adapters and publish certification remain roadmap work. |
| Compliance readiness | Partial | Control mappings and strategy docs exist. No SOC 2, ISO 42001, HIPAA, PCI, GDPR, or EU AI Act certification is claimed. |
| Enterprise support/SLA | Not offered | This repository is single-maintainer and best-effort only. |

## What You Can Safely Claim

- "Reference implementation of governed agentic AI execution."
- "Policy-wrapped deterministic tool execution for high-risk or state-changing tool calls."
- "Provider-neutral core boundary with runtime adapter contracts."
- "Local evaluation stack with SQLite persistence and FastAPI APIs."
- "Architecture checks that enforce provider SDK locality and module boundaries."

## What You Should Not Claim

- "Enterprise-ready platform."
- "Certified compliance product."
- "Production deployment template."
- "Complete multi-provider adapter marketplace."
- "Vendor-backed SaaS."
- "Guaranteed support or SLA."

## Evaluation Checklist

Before evaluating the project, read:

- [README.md](README.md)
- [MAINTAINER_STATUS.md](MAINTAINER_STATUS.md)
- [docs/architecture/governed-execution-pipeline.md](docs/architecture/governed-execution-pipeline.md)
- [docs/strategy/governed-execution-positioning.md](docs/strategy/governed-execution-positioning.md)
- [docs/strategy/next-directions.md](docs/strategy/next-directions.md)

Before using it beyond local evaluation, require a separate hardening pass for:

- datastore choice and migration strategy,
- identity and secrets integration,
- deployment packaging,
- telemetry and incident response,
- compliance evidence,
- operational ownership.

<!--
File: README.md
Path: docs/decisions/README.md
Role: Index of architecture and adapter decisions (ADR-style, evidence-aligned).
Used By:
 - docs/README.md
 - docs/operations/adapter-installation.md
Depends On:
 - docs/plans/tenant-tool-execution-architecture.md
Notes:
 - New decisions: one file per topic, status + date in the doc body.
-->

# Architecture decisions

Short, durable decisions that explain **why** the code behaves a certain way. For implementation status and slices, prefer [tenant-tool-execution-architecture.md](../plans/tenant-tool-execution-architecture.md) and [traceability-matrix.md](../strategy/traceability-matrix.md).

## Decisions

| Decision | Status | Topic |
|---|---|---|
| [submit-tool-results-orchestrator-only.md](submit-tool-results-orchestrator-only.md) | Accepted (adapter **0.1.1**) | OpenAI adapter: orchestrator-owned tool continuation vs in-stream Agents SDK resume |

## Related

| Document | Role |
|---|---|
| [governed-execution-pipeline.md](../architecture/governed-execution-pipeline.md) | Canonical API turn ordering |
| [adapter-installation.md](../operations/adapter-installation.md) | Operator install + `adapter_class_ref` |
| [eXo_adapters packages-reference](https://github.com/SavinRazvan/eXo_adapters/blob/main/docs/packages-reference.md) | Packaged adapter behavior |

## Adding a decision

1. Create `docs/decisions/<short-slug>.md` with file header (`File:`, `Path:`, `Role:`, …).
2. Include **Status**, **Context**, **Decision**, **Consequences**, **References**.
3. Link from this README and from any operator or architecture doc that depends on it.

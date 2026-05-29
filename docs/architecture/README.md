<!--
File: README.md
Path: docs/architecture/README.md
Role: Index for durable architecture documentation under docs/architecture/.
Used By:
 - docs/README.md
Depends On:
 - docs/architecture/ARCHITECTURE.md
 - docs/architecture/governed-execution-pipeline.md
 - docs/architecture/beginner-workflow.md
 - docs/architecture/mvp.md
 - docs/architecture/workspace-architecture.md
Notes:
 - `docs/architecture_mvp.md` is a redirect stub for historical links.
-->

# Architecture documentation

## Recommended reading order

| Order | Document | Audience |
|---|---|---|
| 1 | [beginner-workflow.md](beginner-workflow.md) | Plain-language first pass |
| 2 | [governed-execution-pipeline.md](governed-execution-pipeline.md) | **Canonical turn ordering** (ingress → orchestrator → policy → tools) |
| 3 | [ARCHITECTURE.md](ARCHITECTURE.md) | Full planes map, modules, enforcement |
| 4 | [mvp.md](mvp.md) | One-page layers + guardrails |
| 5 | [workspace-architecture.md](workspace-architecture.md) | Modular monolith doctrine |

**Hands-on (optional):** [notebooks/EVALUATOR_GUIDE.md](../../notebooks/EVALUATOR_GUIDE.md) (15 min / 90 min); full index [notebooks/README.md](../../notebooks/README.md). Standards: [notebook-standards.md](../plans/notebook-standards.md).

---

## Documents

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — ten planes (§2), request path (§3), layers, modules, packages, plans map (§10), enforcement, maintainer checklist (§14).
- **[governed-execution-pipeline.md](governed-execution-pipeline.md)** — API turn stages, `PolicyAction.ESCALATE`, direct-`Orchestrator` bypass warning, **Hands-on proof** (`tutorial_08`).
- **[beginner-workflow.md](beginner-workflow.md)** — beginner analogies mapped to `src/` paths.
- **[mvp.md](mvp.md)** — compact layer list and guardrails.
- **[workspace-architecture.md](workspace-architecture.md)** — module boundaries, adapter independence, enterprise controls.

<!--
File: runtime_contracts.md
Path: docs/runtime_contracts.md
Role: Canonical RuntimeAdapter contract, mode selection, and northbound vs southbound boundaries.
Used By:
 - docs/README.md
 - docs/modules/runtime.md
 - docs/plans/option-c-contract-freeze.md
 - exo_brain_core_contracts (PyPI)
Depends On:
 - exo_brain_core_contracts.runtime_adapter (PyPI: exo-brain-core-contracts)
 - src/runtime/runtime_adapter.py
 - src/runtime/mode_selector.py
 - docs/decisions/submit-tool-results-orchestrator-only.md
Notes:
 - Last reviewed: 2026-05-29
-->

# Runtime contracts

**Status:** active  
**Owner:** Savin I. Razvan

## RuntimeAdapter (southbound provider boundary)

The canonical ABC lives in **`exo-brain-core-contracts`** ([SavinRazvan/eXo_adapters](https://github.com/SavinRazvan/eXo_adapters)). The control plane re-exports it from `src/runtime/runtime_adapter.py` so orchestration and **PyPI adapter wheels** share one type identity.

All provider runtimes implement `RuntimeAdapter`:

| Method | Role |
|---|---|
| `start_session(session_id, metadata=None)` | Bind a provider session handle |
| `run_turn(session_id, user_input, context)` | Stream `RuntimeEvent`s for a user turn |
| `submit_tool_results(session_id, run_id, tool_results)` | Continue after deterministic tool execution |
| `get_capabilities()` | Capability map for mode selection |
| `healthcheck()` | Provider health for registration gates |

**Continuation model:** Tool results are submitted by the **orchestrator** on the governed path; adapters must not silently resume provider-native loops without that contract. See [submit-tool-results-orchestrator-only.md](decisions/submit-tool-results-orchestrator-only.md).

Implementations: in-repo `src/runtime/*` and published wheels (`exo-adapter-openai`, `exo-adapter-echo`, …) loaded via `src/runtime/adapter_factory.py` — [adapter-installation.md](operations/adapter-installation.md).

## Northbound vs southbound boundary

| Boundary | Location | Notes |
|---|---|---|
| **Southbound** | `src/runtime/*` + PyPI adapter packages | Provider SDKs and provider-shaped I/O stay here |
| **Northbound** | `src/api/*` | REST/SSE/WS; tenant routes under `/tenants/...` |
| **Customer bridge** | `POST /v1/chat/completions` | Optional when `EXO_ENABLE_OPENAI_COMPAT_GATEWAY=1`; same governance spine as SSE turns |

A provider can be OpenAI-compatible **southbound** without exposing a public OpenAI-compatible **northbound** API. Northbound OpenAI-shaped traffic is a gateway concern (`src/api/routers/openai_gateway.py`), not the adapter ABC.

Customer wire reference: [customer-api-integration-guide.md](api/customer-api-integration-guide.md).

## Interaction mode ownership

| Mode | Primary owner | Runtime responsibility |
|---|---|---|
| `chat` (completions-style) | API gateway + runtime adapter | Execute model turns; normalize events |
| `agents` (Agents SDK style) | Runtime adapter | Agent-native turns; emit tool intent/output events |
| `workflow` (multi-step) | `src/core/*` orchestration | Coordinate graphs/steps; runtime executes individual turns only |

Workflow definitions: [workflow_loading.md](workflow_loading.md). Orchestration detail: [docs/modules/core.md](modules/core.md).

## Core constraints

- Core orchestration consumes only runtime contract types (no provider SDK imports in `src/core/`).
- Runtime adapters normalize provider output into internal events (`src/schemas/events.py`).
- Runtime adapters do **not** own ingress or tool policy decisions.
- Policy middleware wraps state-changing tool paths regardless of entry mode ([governed-execution-pipeline.md](architecture/governed-execution-pipeline.md)).

## Mode selection

Implemented in `src/runtime/mode_selector.py`:

- **`provider_native`** — only when capability map + policy allow **and** the call is not state-changing / high-risk.
- **`deterministic`** — required for state-changing, high-impact, or uncertain capability paths.
- Policy `deny` / `escalate` or capability uncertainty → **deterministic** (safe fallback).

## Required event behavior

- Preserve correlation fields where applicable (`session_id`, `run_id`, `job_id`, `task_id`, `agent_id`, `provider_id`).
- Emit structured completion envelopes and normalized failure metadata.
- Keep envelope shape stable across chat, agents, and workflow entry paths.

## Tests (anchors)

- `tests/modules/runtime/test_runtime_adapter_contract.py`
- `tests/modules/runtime/test_mode_selector.py`
- `tests/packages/test_openai_adapter_conformance.py`

## Related

- [docs/modules/runtime.md](modules/runtime.md)
- [docs/architecture/mvp.md](architecture/mvp.md)
- [docs/plans/option-c-contract-freeze.md](plans/option-c-contract-freeze.md)

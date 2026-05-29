<!--
File: runtime.md
Path: docs/modules/runtime.md
Role: Module-level contract and maintenance guide for runtime adapters and tenant runtime composition.
Used By:
 - docs/modules/README.md
 - Maintainers modifying provider adapters and runtime mode selection
Depends On:
 - src/runtime/
 - packages/eXo_adapters/ (published adapter source; in-tree copy)
 - tests/modules/runtime/
 - tests/packages/
Notes:
 - Provider SDKs and packaged adapters load only through adapter_factory / registry paths.
-->

# Runtime Module

## Metadata

- Status: `active`
- Owner: Savin I. Razvan
- Last validated commit: `HEAD`
- Last reviewed: `2026-05-29`

## Primary Code Paths

- `src/runtime/runtime_adapter.py` — canonical adapter interface
- `src/runtime/adapter_factory.py` — `adapter_class_ref` resolution (in-repo + PyPI entry points)
- `src/runtime/capability_map.py` — capability handshake for routing
- `src/runtime/mode_selector.py` — deterministic vs provider-native mode (capability + policy)
- `src/runtime/tenant_runtime.py` — per-tenant registry composition (tools, agents, adapter instance)
- `src/runtime/tool_wiring.py` — bind tools to runtime execution
- `src/runtime/openai_agents_runtime.py` — in-repo OpenAI Agents SDK adapter (may delegate to packaged `exo-adapter-openai`)
- `src/runtime/openai_compatible_runtime.py`, `src/runtime/custom_runtime.py` — additional adapter shapes
- `src/modules/provider_management/service.py` — provider registration persistence seam
- `src/modules/session_runtime/service.py` — session create + runtime cache (`src/api/routers/sessions.py`)

**Packaged adapters (authoritative releases):** [`packages/eXo_adapters/`](../../packages/eXo_adapters/) → PyPI (`exo-brain-adapter-sdk`, `exo-adapter-openai`, `exo-adapter-echo`, etc.). Canonical `adapter_class_ref` table: [adapter-installation.md](../operations/adapter-installation.md).

## Primary Tests

- `tests/modules/runtime/` — contract, factory, mode selector, tenant runtime, packaged E2E
- `tests/packages/test_openai_adapter_conformance.py` — packaged adapter conformance
- **Anchors:** `test_runtime_adapter_contract.py`, `test_adapter_factory.py`, `test_packaged_adapter_e2e.py`, `test_tenant_runtime.py`

## Contract Boundaries

- Runtime contract methods:
  - `start_session`
  - `run_turn`
  - `submit_tool_results` (orchestrator-owned continuation — see [submit-tool-results-orchestrator-only.md](../decisions/submit-tool-results-orchestrator-only.md))
  - `get_capabilities`
  - `healthcheck`
- Provider-specific code stays in **adapter modules** only (in-repo or PyPI); core/policies/tools must not import SDKs.
- Mode selection is **capability + policy** driven, never provider-name hardcoded.
- Runtime adapters normalize provider output to internal events; they do **not** own ingress or tool policy decisions.

## Operational Links

- [runtime_contracts.md](../runtime_contracts.md)
- [adapter-installation.md](../operations/adapter-installation.md)
- [adapter-repos-and-pypi.md](../operations/adapter-repos-and-pypi.md)
- [option-c-contract-freeze.md](../plans/option-c-contract-freeze.md)
- [option-c-worker-isolation-contract.md](../plans/option-c-worker-isolation-contract.md)

## Breaking-Change Policy

- Any runtime contract signature or event behavior change requires:
  - conformance tests update (`tests/modules/runtime/`, `tests/packages/`)
  - docs update (`docs/runtime_contracts.md`, this file, customer guide if northbound-visible)
  - verification on at least two adapter implementations (e.g. echo + openai packaged)

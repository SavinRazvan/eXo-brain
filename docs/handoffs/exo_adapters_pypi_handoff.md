<!--
File: exo_adapters_pypi_handoff.md
Path: docs/handoffs/exo_adapters_pypi_handoff.md
Role: Completion status for adapter package extraction — points to in-tree packages and operator docs.
Used By:
 - docs/handoffs/README.md
Depends On:
 - packages/eXo_adapters/
 - docs/operations/adapter-repos-and-pypi.md
 - docs/operations/adapter-installation.md
 - docs/plans/adapter-packages-extraction-handoff.md
Notes:
 - Supersedes the 2026-03 “create eXo_adapters repo” mission playbook (see docs/archive/handoffs/).
-->

# Adapter packages handoff — **completed**

**Status:** Done for the core mission (2026-05).  
**Do not use this file as an implementation playbook** — use the canonical docs below.

---

## What was delivered

| Deliverable | Location |
|---|---|
| **Four PyPI distributions** (lockstep **0.1.1**) | `exo-brain-core-contracts`, `exo-brain-adapter-sdk`, `exo-adapter-echo`, `exo-adapter-openai` |
| **Authoring / publish tree** | [`packages/eXo_adapters/`](../../packages/eXo_adapters/) (in-tree copy of the adapter ecosystem repo) |
| **Public GitHub repo** | [SavinRazvan/eXo_adapters](https://github.com/SavinRazvan/eXo_adapters) |
| **eXo-brain consumes contracts from PyPI** | `requirements.txt` → `exo-brain-core-contracts==0.1.1` |
| **Optional adapters from PyPI** | `requirements-adapters.txt` (all three adapter distributions at 0.1.1) |
| **Dev install fallback** | `scripts/dev/install_adapter_dependencies.sh` → editable installs under `packages/eXo_adapters/packages/` |
| **Conformance tests in control plane** | `tests/packages/test_*_adapter_conformance.py` |
| **Conformance + CI in adapter tree** | `packages/eXo_adapters/tests/`, `packages/eXo_adapters/scripts/` |

---

## Canonical docs (use these)

| Audience | Document |
|---|---|
| **Operators** (pip install, register providers) | [docs/operations/adapter-installation.md](../operations/adapter-installation.md) |
| **Repo / PyPI layout** | [docs/operations/adapter-repos-and-pypi.md](../operations/adapter-repos-and-pypi.md) |
| **Adapter maintainers** (authoring, releases) | [packages/eXo_adapters/README.md](../../packages/eXo_adapters/README.md), [RELEASE.md](../../packages/eXo_adapters/RELEASE.md) |
| **Inventory + remaining cleanup** | [docs/plans/adapter-packages-extraction-handoff.md](../plans/adapter-packages-extraction-handoff.md) |
| **Runtime ADR** (`submit_tool_results`) | [docs/decisions/submit-tool-results-orchestrator-only.md](../decisions/submit-tool-results-orchestrator-only.md) |

---

## `adapter_class_ref` (unchanged)

| Adapter | Dotted path |
|---|---|
| OpenAI | `exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter` |
| Echo | `exo_adapter_echo.runtime.EchoRuntimeAdapter` |

Loaded via [`src/runtime/adapter_factory.py`](../../src/runtime/adapter_factory.py).

---

## Optional follow-ups (not blocking “handoff done”)

Tracked in [adapter-packages-extraction-handoff.md](../plans/adapter-packages-extraction-handoff.md) §9:

- Remove in-tree `packages/eXo_adapters/` from eXo-brain once every environment uses PyPI-only installs (dev clones can use a sibling checkout of `eXo_adapters`).
- Narrow `scan_forbidden_imports` / CI paths that still scan vendored `packages/**`.
- Decide long-term fate of in-tree `src/runtime/openai_agents_runtime.py` fallback when package-only path is proven everywhere.

---

## Historical mission playbook

The original “create repo + publish PyPI + wire eXo-brain” step-by-step mission is **archived**: [docs/archive/handoffs/exo_adapters_pypi_handoff-mission.md](../archive/handoffs/exo_adapters_pypi_handoff-mission.md).

<!--
File: exo_adapters_pypi_handoff.md
Path: docs/handoffs/exo_adapters_pypi_handoff.md
Role: Completion status for adapter package extraction — PyPI-only consumption in eXo-brain.
Used By:
 - docs/handoffs/README.md
Depends On:
 - docs/operations/adapter-repos-and-pypi.md
 - docs/operations/adapter-installation.md
 - docs/plans/adapter-packages-extraction-handoff.md
Notes:
 - Supersedes the 2026-03 “create eXo_adapters repo” mission playbook (see docs/archive/handoffs/).
-->

# Adapter packages handoff — **completed**

**Status:** Done for the core mission (2026-05). In-tree `packages/eXo_adapters/` removed; eXo-brain installs wheels from PyPI only.

---

## What was delivered

| Deliverable | Location |
|---|---|
| **Four PyPI distributions** (lockstep; see `requirements.txt`) | `exo-brain-core-contracts`, `exo-brain-adapter-sdk`, `exo-adapter-echo`, `exo-adapter-openai` |
| **Authoring / publish repo** | [SavinRazvan/eXo_adapters](https://github.com/SavinRazvan/eXo_adapters) |
| **eXo-brain install** | `requirements.txt` (all four distributions; current lockstep **0.1.1**) |
| **Optional adapters-only file** | `requirements-adapters.txt` (when contracts already satisfied) |
| **Dev install** | `bash scripts/dev/install_adapter_dependencies.sh` → PyPI via `requirements.txt` |
| **Conformance tests in control plane** | `tests/packages/test_*_adapter_conformance.py` |
| **Conformance + CI in adapter repo** | `eXo_adapters/tests/`, `eXo_adapters/scripts/` |

---

## Canonical docs (use these)

| Audience | Document |
|---|---|
| **Operators** (pip install, register providers) | [docs/operations/adapter-installation.md](../operations/adapter-installation.md) |
| **Repo / PyPI layout** | [docs/operations/adapter-repos-and-pypi.md](../operations/adapter-repos-and-pypi.md) |
| **Adapter maintainers** (authoring, releases) | [eXo_adapters README](https://github.com/SavinRazvan/eXo_adapters/blob/main/README.md), [RELEASE.md](https://github.com/SavinRazvan/eXo_adapters/blob/main/RELEASE.md) |
| **Inventory + cleanup history** | [docs/plans/adapter-packages-extraction-handoff.md](../plans/adapter-packages-extraction-handoff.md) |
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

- Publish automation hardening in `eXo_adapters`.
- Lane A universal adapter package.

---

## Historical mission playbook

The original “create repo + publish PyPI + wire eXo-brain” step-by-step mission is **archived**: [docs/archive/handoffs/exo_adapters_pypi_handoff-mission.md](../archive/handoffs/exo_adapters_pypi_handoff.md).

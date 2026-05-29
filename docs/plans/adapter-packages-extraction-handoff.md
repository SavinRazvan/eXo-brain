<!--
File: adapter-packages-extraction-handoff.md
Path: docs/plans/adapter-packages-extraction-handoff.md
Role: Complete inventory and migration checklist for moving `packages/` adapter ecosystem to a separate repository (e.g. `ai-adapters-sdk`).
Used By:
 - Maintainers splitting the monorepo
 - Implementers in the adapter repo
Depends On:
 - **eXo_adapters** repository (`packages/*` layout inside that repo)
 - scripts/packages/external_install_smoke.py
 - tests/packages/*
 - src/runtime/adapter_factory.py
 - docs/strategy/adapter-compatibility-matrix.md
 - docs/strategy/governed-execution-positioning.md (Repository boundary)
Notes:
 - eXo-brain no longer vendors adapter sources; this doc stays the inventory for **eXo_adapters** maintainers.
-->

# Adapter packages extraction handoff (`packages/` → **eXo_adapters**)

**Status (2026-05-29):** **Complete.** Adapter source lives in [SavinRazvan/eXo_adapters](https://github.com/SavinRazvan/eXo_adapters); eXo-brain consumes **PyPI lockstep** pins in `requirements.txt` / `requirements-adapters.txt` (no in-tree `packages/`). **Completion summary:** [docs/handoffs/exo_adapters_pypi_handoff.md](../handoffs/exo_adapters_pypi_handoff.md). **Operators:** [adapter-installation.md](../operations/adapter-installation.md).

---

## 1. Goal

Portable adapter artifacts live in the **eXo_adapters** repository (multi-package layout, same PyPI distribution names). The eXo-brain repo remains **control plane only**; it **consumes** `exo-brain-core-contracts` (and optional adapters) via **pip** (git or PyPI) and loads runtime implementations via **`adapter_class_ref`** (`src/runtime/adapter_factory.py`).

**Layout:** path columns below use **`packages/...`** as inside **eXo_adapters**. An optional **`moving_to_adapters_project/`** copy may exist only as a migration aid; it is not required for eXo-brain CI once `requirements.txt` points at the real remote.

---

## 2. What moves (complete file inventory)

**Do not copy** `*.egg-info/` trees — they are build outputs; add `*.egg-info/` to `.gitignore` in the new repo.

### 2.1 `exo-brain-core-contracts` (distribution name: `exo-brain-core-contracts`)

| Path (repo-relative) | Role |
|----------------------|------|
| `packages/exo-brain-core-contracts/pyproject.toml` | Setuptools project, `package-dir = src`, Python `>=3.11` (consider aligning to **3.12** with control plane). |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/__init__.py` | Public exports (stable `__all__`). |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/runtime_adapter.py` | **`RuntimeAdapter` ABC**, `SessionHandle` — **v1 compatibility anchor** (semver majors break here). |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/events.py` | `RuntimeEvent`, `RuntimeEventType` (+ streaming factory classmethods). |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/tool_io.py` | Tool envelopes, `ToolCallContext`, `ToolResult`, policy/risk enums, `blocked_result`. |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/capability_map.py` | `ProviderCapabilityMap`, `HealthStatus`, tiers. |

**Contract rule:** Keep method signatures on `RuntimeAdapter` aligned with what the control plane orchestrator expects (`start_session`, `run_turn`, `submit_tool_results`, `get_capabilities`, `healthcheck`).

### 2.2 `exo-brain-adapter-sdk` (distribution name: `exo-brain-adapter-sdk`)

| Path | Role |
|------|------|
| `packages/exo-brain-adapter-sdk/pyproject.toml` | Depends on **`exo-brain-core-contracts`** (PEP 508 name). |
| `packages/exo-brain-adapter-sdk/src/exo_brain_adapter_sdk/__init__.py` | Exports: `assert_runtime_adapter_contract`, `AdapterToolDescriptor`, `ToolExecutionAdapterContract`. |
| `packages/exo-brain-adapter-sdk/src/exo_brain_adapter_sdk/execution_adapter.py` | Tool execution adapter helpers. |
| `packages/exo-brain-adapter-sdk/src/exo_brain_adapter_sdk/conformance/__init__.py` | Package marker. |
| `packages/exo-brain-adapter-sdk/src/exo_brain_adapter_sdk/conformance/runtime_adapter_contract.py` | **Structural** conformance (async methods + `get_capabilities`); no network. |

**Refactor note:** `exo-adapter-openai` does **not** declare a dependency on `exo-brain-adapter-sdk` in `pyproject.toml` today; conformance is test-time only. In the new repo, consider **`optional` dev extra** or document “adapter authors install `exo-brain-adapter-sdk` for testing.”

### 2.3 `exo-adapter-openai` (distribution name: `exo-adapter-openai`)

| Path | Role |
|------|------|
| `packages/exo-adapter-openai/pyproject.toml` | Depends on `exo-brain-core-contracts`, `openai>=1.0.0`, `openai-agents>=0.0.0`. |
| `packages/exo-adapter-openai/src/exo_adapter_openai/__init__.py` | Exports: `OpenAIAgentsRuntimeAdapter`, `load_adapter`, `build_agent_tools`. |
| `packages/exo-adapter-openai/src/exo_adapter_openai/runtime.py` | Main **`RuntimeAdapter`** implementation; uses **only** `exo_brain_core_contracts` + local `tool_wiring`. |
| `packages/exo-adapter-openai/src/exo_adapter_openai/tool_wiring.py` | Agent/tool wiring for OpenAI Agents SDK path. |

**Portability rule:** No `from src.` / `import src` (enforced today by `tests/packages/test_openai_adapter_conformance.py` and `scripts/architecture/scan_forbidden_imports.py` in eXo-brain).

### 2.4 `exo-adapter-echo` (distribution name: `exo-adapter-echo`)

| Path | Role |
|------|------|
| `packages/exo-adapter-echo/pyproject.toml` | Depends on `exo-brain-core-contracts` only. |
| `packages/exo-adapter-echo/src/exo_adapter_echo/__init__.py` | Export `EchoRuntimeAdapter`, `load_adapter`. |
| `packages/exo-adapter-echo/src/exo_adapter_echo/runtime.py` | Deterministic echo adapter (no external I/O); second adapter for parity/smoke. |

---

## 3. Install order (editable / isolated venv)

**Order matters** for local dev installs (same as `scripts/packages/external_install_smoke.py`):

1. `exo-brain-core-contracts`
2. `exo-brain-adapter-sdk`
3. `exo-adapter-echo`
4. `exo-adapter-openai`

**Smoke script to relocate:** `scripts/packages/external_install_smoke.py` — either **move** into `ai-adapters-sdk` as `scripts/external_install_smoke.py` with `REPO_ROOT` pointing at the new repo root, or keep a thin wrapper in eXo-brain that clones/pins the adapter repo (post-extraction).

Assertions inside the smoke script today:

- Import `exo_brain_core_contracts` exports.
- Import `exo_brain_adapter_sdk` exports.
- Import `exo_adapter_openai` and `exo_adapter_echo` + `load_adapter` factories.
- **`module_origin`:** OpenAI adapter class module must **not** start with `src.` (monorepo leak guard).
- `assert_runtime_adapter_contract` on both adapters.
- Minimal `asyncio.run` on OpenAI adapter `run_turn` expecting `output_delta` and `run_complete` event types.

---

## 4. Tests to move (or mirror)

| Path | Purpose |
|------|---------|
| `tests/packages/test_core_contracts_imports.py` | Inserts `packages/.../src` on `sys.path`; replace with **installed** package tests after extraction. |
| `tests/packages/test_openai_adapter_conformance.py` | Conformance, `load_adapter`, no-monorepo-import scan, portability `run_turn`. |
| `tests/packages/test_echo_adapter_conformance.py` | Same for echo. |

**After extraction (eXo-brain side):** Replace with either:

- **Optional** integration job: `pip install` published adapters + run a **small** subset of contract tests, or  
- **Submodule / workspace** checkout of `ai-adapters-sdk` in CI only (policy decision).

---

## 5. Control plane coupling (eXo-brain — what you must preserve)

### 5.1 `src/runtime/adapter_factory.py` (current — post-extraction)

- **Canonical class refs:**
  - `exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter`
  - `exo_adapter_echo.runtime.EchoRuntimeAdapter`
- **Loading:** `importlib` only — **no in-tree adapter fallback**. Missing wheels raise `ImportError` with install hints (`requirements.txt` / `install_adapter_dependencies.sh`).
- **Type check:** `_load_adapter_class` uses **`issubclass(cls, RuntimeAdapter)`** where **`src.runtime.runtime_adapter.RuntimeAdapter`** is the **same class object** as **`exo_brain_core_contracts.runtime_adapter.RuntimeAdapter`** (re-export; see **STP-W4-002**).

**Remaining control-plane-only envelopes (not in contracts package):**

- **`src/schemas/outputs.py`**, **`workflow_schema.py`**, and other non-runtime envelopes remain in-tree only.

**Extraction exit criterion:** **Met** — with pip-installed packages only, `load_adapter("exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter", provider_id=...)` succeeds and orchestration works.

### 5.2 Control-plane re-exports (not duplicate adapters)

- `src/runtime/runtime_adapter.py` — **re-exports** published `RuntimeAdapter` / `SessionHandle` (no parallel ABC).
- `src/schemas/events.py`, `src/schemas/tool_io.py`, `src/runtime/capability_map.py` — **re-exports** published envelopes (**STP-W4-003**); drift guarded by `tests/modules/runtime/test_contract_drift.py`.
- `src/runtime/openai_agents_runtime.py` — **thin shim** re-exporting `exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter` (stable import path for notebooks/tests).

### 5.3 Provider registration / hydration

- `src/api/routers/providers.py`, `src/api/startup.py`, `src/config/provider_registry.py` persist **`adapter_class_ref`** strings consumed by `load_adapter`.

No change to **API shape** required for extraction if **dotted class paths** stay stable.

### 5.4 Architecture enforcement in eXo-brain

- `scripts/architecture/scan_forbidden_imports.py` — **narrowed** after extraction (no in-tree `packages/exo-adapter-*/src` scan).
- `.github/workflows/architecture-fitness.yml` — installs adapters from PyPI via `install_adapter_dependencies.sh`; runs `pytest tests/packages` against **installed** wheels.

---

## 6. Documentation and matrices (post-move — **done 2026-05-29**)

| Doc | Status |
|-----|--------|
| `docs/strategy/adapter-compatibility-matrix.md` | Updated — PyPI **0.1.2**, eXo_adapters repo |
| `docs/strategy/adapter-strategy.md` | Updated — extraction complete |
| `docs/architecture/ARCHITECTURE.md` | Updated — PyPI adapter plane |
| `README.md` | Updated — PyPI install path |
| `docs/strategy/traceability-matrix.md` | Updated — no transitional `packages/` |

---

## 7. eXo_adapters repository layout (actual)

Single repo, multiple distributions (matches current mental model):

```text
eXo_adapters/
  packages/exo-brain-core-contracts/   # or flatten to exo-brain-core-contracts/ at root
  packages/exo-brain-adapter-sdk/
  packages/exo-adapter-openai/
  packages/exo-adapter-echo/
  scripts/external_install_smoke.py
  tests/
    test_core_contracts_imports.py
    test_openai_adapter_conformance.py
    test_echo_adapter_conformance.py
  .github/workflows/   # pytest + smoke on PR
  README.md            # install order, versioning, link to eXo-brain control plane
```

Alternatively: **one** `pyproject.toml` with **workspace** / multiple packages (Poetry/uv/hatch) — tooling choice is yours; keep **distribution names** stable for `pip install exo-adapter-openai`.

---

## 8. Versioning and release

- **Semver:** Follow `docs/strategy/adapter-compatibility-matrix.md` §2.
- **Pinning in eXo-brain:** Add to `requirements.txt` (or optional extra) e.g. `exo-brain-core-contracts==x.y.z`, `exo-adapter-openai==x.y.z` once on PyPI; until then `pip install git+https://...` or submodule.
- **Breaking change process:** Bump **contracts** major → bump SDK + all adapters’ declared compatible range; document in matrix.

---

## 9. Refactor checklist (before deleting `packages/` from eXo-brain)

1. [x] New repo created; all sources + tests + smoke script migrated; CI green (`packages/eXo_adapters/`).  
2. [x] `external_install_smoke` / adapter repo smoke passes (`packages/eXo_adapters/scripts/external_install_smoke.py`).  
3. [x] eXo-brain **`load_adapter`** uses package path **without** relying on in-tree fallback (or fallback explicitly deprecated).  
4. [x] **Published runtime type identity** — **STP-W4-002** + **STP-W4-003** (contracts **0.1.1+**).  
5. [x] `requirements.txt` / `requirements-adapters.txt` pin PyPI **0.1.2**; Docker uses `install_adapter_dependencies.sh`.  
6. [x] Remove `packages/eXo_adapters/` from eXo-brain; dev uses sibling clone or PyPI.  
7. [x] Narrow `scan_forbidden_imports` / CI `packages/**` triggers once vendored tree is dev-only.  
8. [x] Operator docs: `adapter-installation.md`, `adapter-repos-and-pypi.md`, handoff status doc.

---

## 10. Quick reference — PyPI names and dependencies

| Distribution | Version (today) | `requires-python` | Runtime deps (declared) |
|--------------|-----------------|-------------------|-------------------------|
| `exo-brain-core-contracts` | 0.1.2 | >=3.11 | — |
| `exo-brain-adapter-sdk` | 0.1.2 | >=3.11 | `exo-brain-core-contracts` |
| `exo-adapter-openai` | 0.1.2 | >=3.11 | `exo-brain-core-contracts`, `openai`, `openai-agents` |
| `exo-adapter-echo` | 0.1.2 | >=3.11 | `exo-brain-core-contracts` |

---

## 11. Revision

| Date | Change |
|------|--------|
| 2026-05-29 | PyPI-only eXo-brain: in-tree `packages/` removed; lockstep **0.1.2**; checklist §9 items 3, 5, 7 closed; §10 version table updated. |
| 2026-03-27 | **STP-W4-002:** `requirements.txt` + Dockerfile install editable `exo-brain-core-contracts`; `runtime_adapter.py` re-exports published ABC; factory uses single `issubclass`; checklist §9 item 4 closed for RuntimeAdapter identity; §5.1–5.2 refreshed. |
| 2026-03-27 | Factory: `_is_acceptable_runtime_adapter_subclass` accepts published `exo_brain_core_contracts.RuntimeAdapter` when importable (STP-W4-001); handoff §5.1 debt note refreshed. |
| 2026-03-24 | Initial handoff: full inventory, install order, smoke script contract, factory coupling, dual-ABC debt, migration phases. |

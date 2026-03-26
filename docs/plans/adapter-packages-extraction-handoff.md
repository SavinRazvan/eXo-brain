<!--
File: adapter-packages-extraction-handoff.md
Path: docs/plans/adapter-packages-extraction-handoff.md
Role: Complete inventory and migration checklist for moving `packages/` adapter ecosystem to a separate repository (e.g. `ai-adapters-sdk`).
Used By:
 - Maintainers splitting the monorepo
 - Implementers in the adapter repo
Depends On:
 - packages/* (current source)
 - scripts/packages/external_install_smoke.py
 - tests/packages/*
 - src/runtime/adapter_factory.py
 - docs/strategy/adapter-compatibility-matrix.md
 - docs/strategy/governed-execution-positioning.md (Repository boundary)
Notes:
 - Does not perform the move; use as a build/refactor contract before deleting `packages/` from eXo-brain.
-->

# Adapter packages extraction handoff (`packages/` → `ai-adapters-sdk`)

## 1. Goal

Move **all portable adapter artifacts** out of the eXo-brain monorepo into a **dedicated project** (working name: **`ai-adapters-sdk`**, or a multi-package repo containing the same PyPI-named distributions). The eXo-brain repo remains **control plane only**; it **consumes** published (or git-pinned) adapter wheels and continues to load adapters via **`adapter_class_ref`** (`src/runtime/adapter_factory.py`).

---

## 2. What moves (complete file inventory)

**Do not copy** `*.egg-info/` trees — they are build outputs; add `*.egg-info/` to `.gitignore` in the new repo.

### 2.1 `exo-brain-core-contracts` (distribution name: `exo-brain-core-contracts`)

| Path (repo-relative) | Role |
|----------------------|------|
| `packages/exo-brain-core-contracts/pyproject.toml` | Setuptools project, `package-dir = src`, Python `>=3.11` (consider aligning to **3.12** with control plane). |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/__init__.py` | Public exports (stable `__all__`). |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/runtime_adapter.py` | **`RuntimeAdapter` ABC**, `SessionHandle` — **v1 compatibility anchor** (semver majors break here). |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/events.py` | `RuntimeEvent`, `RuntimeEventType`. |
| `packages/exo-brain-core-contracts/src/exo_brain_core_contracts/tool_io.py` | Tool envelopes, `ToolCallContext`, `ToolResult`, policy/risk enums. |
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

### 5.1 `src/runtime/adapter_factory.py`

- **Canonical class refs:**
  - `exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter`
  - `exo_adapter_echo.runtime.EchoRuntimeAdapter`
- **Fallback chains** (try in order until one loads):
  - OpenAI: package class → `src.runtime.openai_agents_runtime.OpenAIAgentsRuntimeAdapter` → `exo_adapter_openai.OpenAIAgentsRuntimeAdapter`
  - Echo: package class → `src.runtime.openai_compatible_runtime.OpenAICompatibleRuntimeAdapter`
- **Type check:** `_load_adapter_class` requires `issubclass(cls, src.runtime.runtime_adapter.RuntimeAdapter)` (the **in-tree** ABC).

**Critical technical debt (document for refactor):**

- Package adapters subclass **`exo_brain_core_contracts.RuntimeAdapter`**.
- The factory validates against **`src.runtime.runtime_adapter.RuntimeAdapter`**.
- Today, if `exo_adapter_openai` is **not** importable (typical bare venv), the factory **silently falls back** to the **in-tree** `OpenAIAgentsRuntimeAdapter`. Once adapters are **only** on PyPI, you must either:
  - **Unify** on one ABC (e.g. control plane depends on published `exo-brain-core-contracts` and uses that `RuntimeAdapter` in `issubclass`), or  
  - **Relax** the check to structural typing / duck typing aligned with `assert_runtime_adapter_contract`, or  
  - **Register** a small shim in-tree that inherits **both** (not ideal).

**Extraction exit criterion:** With **only** pip-installed packages (no in-tree duplicate), `load_adapter("exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter", provider_id=...)` must succeed and orchestration must work.

### 5.2 In-tree duplicates (related, not in `packages/`)

- `src/runtime/runtime_adapter.py` — **mirrors** contracts package (parallel ABC).
- `src/runtime/openai_agents_runtime.py` — **parallel** OpenAI adapter used when package import fails or as fallback.

**Post-extraction strategy (choose one):**

1. Keep in-tree implementations as **deprecated** shims until package-only path is proven; then delete.  
2. Make in-tree modules **thin wrappers** that delegate to installed packages (single source of truth).

### 5.3 Provider registration / hydration

- `src/api/routers/providers.py`, `src/api/startup.py`, `src/config/provider_registry.py` persist **`adapter_class_ref`** strings consumed by `load_adapter`.

No change to **API shape** required for extraction if **dotted class paths** stay stable.

### 5.4 Architecture enforcement in eXo-brain

- `scripts/architecture/scan_forbidden_imports.py` — scans `packages/exo-adapter-*/src` for `src.*` imports. After removal of `packages/`, **delete or narrow** this branch.
- `.github/workflows/architecture-fitness.yml` — job `package_workspace_tests` runs `pytest tests/packages`; replace with **published-package** smoke or **matrix job** against `ai-adapters-sdk` checkout.

---

## 6. Documentation and matrices to update after move

| Doc | Update |
|-----|--------|
| `docs/strategy/adapter-compatibility-matrix.md` | §1 “Published packages” → repo URL + PyPI; CI anchors. |
| `docs/strategy/adapter-strategy.md` | Paths `packages/*` → new repo. |
| `docs/architecture/ARCHITECTURE.md` | Adapter plane points to external repo + pins. |
| `README.md` | “Transitional `packages/`” → “install adapters from …”. |
| `docs/strategy/traceability-matrix.md` | Code anchors for adapter split. |

---

## 7. Suggested `ai-adapters-sdk` repository layout

Single repo, multiple distributions (matches current mental model):

```text
ai-adapters-sdk/
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

1. [ ] New repo created; all sources + tests + smoke script migrated; CI green.  
2. [ ] `external_install_smoke` passes in **clean** venv from new repo.  
3. [ ] eXo-brain installs adapters from new location; **`load_adapter`** uses package path **without** relying on in-tree fallback (or fallback explicitly deprecated).  
4. [ ] Resolve **`RuntimeAdapter` ABC duplication** (factory `issubclass` vs `exo_brain_core_contracts`).  
5. [ ] Update `requirements.txt` / Docker image to include adapter packages.  
6. [ ] Remove `packages/` from eXo-brain; remove `tests/packages` or replace with integration smoke.  
7. [ ] Update `scan_forbidden_imports`, `architecture-fitness.yml`, `check_governance_consistency` inputs if they reference `packages/**`.  
8. [ ] Refresh strategy/architecture docs and `adapter-compatibility-matrix.md` with **new repo URL** and release process.

---

## 10. Quick reference — PyPI names and dependencies

| Distribution | Version (today) | `requires-python` | Runtime deps (declared) |
|--------------|-----------------|-------------------|-------------------------|
| `exo-brain-core-contracts` | 0.1.0 | >=3.11 | — |
| `exo-brain-adapter-sdk` | 0.1.0 | >=3.11 | `exo-brain-core-contracts` |
| `exo-adapter-openai` | 0.1.0 | >=3.11 | `exo-brain-core-contracts`, `openai`, `openai-agents` |
| `exo-adapter-echo` | 0.1.0 | >=3.11 | `exo-brain-core-contracts` |

---

## 11. Revision

| Date | Change |
|------|--------|
| 2026-03-24 | Initial handoff: full inventory, install order, smoke script contract, factory coupling, dual-ABC debt, migration phases. |

<!--
File: adapter-compatibility-matrix.md
Path: docs/strategy/adapter-compatibility-matrix.md
Role: Published package versions, supported pairings, semver rules, and M0/M1 implementation status vs adapter-strategy milestones.
Used By:
 - docs/strategy/adapter-strategy.md
 - Maintainers changing packages/** or provider registration
Depends On:
 - packages/*/pyproject.toml
 - docs/strategy/adapter-strategy.md §13, §19.6
Notes:
 - Update this file when bumping package versions or certifying new adapter releases.
-->

# Adapter compatibility matrix

Companion to [`adapter-strategy.md`](adapter-strategy.md) (packaging, certification, lanes). This document is the **single table** for **what is published today** and **what must stay compatible**.

## 1) Published packages (monorepo)

| Package | PyPI name (target) | Version (pyproject) | Python (package) | Depends on |
|--------|-------------------|---------------------|------------------|------------|
| Core contracts | `exo-brain-core-contracts` | **0.1.0** | >=3.11 | — |
| Adapter SDK | `exo-brain-adapter-sdk` | **0.1.0** | >=3.11 | `exo-brain-core-contracts` |
| OpenAI adapter | `exo-adapter-openai` | **0.1.0** | >=3.11 | `exo-brain-core-contracts`, OpenAI SDKs |
| Echo adapter | `exo-adapter-echo` | **0.1.0** | >=3.11 | `exo-brain-core-contracts` |

**Repo platform Python:** minimum **3.12** for `src/**` CI and runtime (see root `README.md`); packages still declare `>=3.11` until a coordinated bump.

## 2) Semver rules (contracts vs SDK vs adapters)

| Artifact | Semver meaning | Breaking change examples |
|----------|----------------|---------------------------|
| **`exo-brain-core-contracts`** | **Major:** incompatible `RuntimeAdapter` method shapes, event/tool envelope breaking changes, removed types. **Minor:** additive fields/enums, backward-compatible defaults. **Patch:** docs-only or internal fixes with no contract surface change. | Removing `run_turn`, changing `RuntimeEvent` required fields |
| **`exo-brain-adapter-sdk`** | Tracks **compatible core-contract range** in package metadata/docs; major bump when helpers assume a new **minimum** contracts major. | Dropping support for contracts 0.x |
| **`exo-adapter-*`** | **Major:** new minimum contracts/SDK, or behavior change visible through core. **Minor:** provider feature parity, non-breaking config. **Patch:** bugfix, retry tuning. | Changing default base URL behavior without API schema update |

**Runtime code comment anchor:** `packages/exo-brain-core-contracts/.../runtime_adapter.py` — keep public method signatures stable for **v1** consumers; use semver + matrix rows when intentionally breaking.

**Publishing rule:** never ship an adapter version that depends on undocumented `src/**` internals (see [`adapter-strategy.md`](adapter-strategy.md) §14).

## 3) M0 milestone status (`api_type` explicitness)

M0 is defined in [`adapter-strategy.md` §19.6](adapter-strategy.md#196-incremental-milestones-implementation-later).

| Acceptance item | Status | Code / test anchors |
|-----------------|--------|---------------------|
| Registration API accepts explicit `api_type` | **Done** | `src/api/schemas/provider_schemas.py` (`ProviderRegisterRequest.api_type`, default `openai_native`) |
| Supported protocol values validated | **Done** | `EndpointApiType` in `src/config/provider_registry.py` (`openai_native`, `openai_compatible`, `custom`); `ProviderManagementService._parse_api_type` in `src/modules/provider_management/service.py` |
| Persisted and hydrated | **Done** | `src/persistence/adapters/sqlite.py` (`endpoint_api_type` column); `src/api/startup.py` hydration |
| API coverage | **Done** | `tests/modules/api/test_slice_provider_registration.py` |

**Remaining (not M0):** universal **Lane A** adapter **package** (M1) — separate from registration explicitness. Northbound **`POST /v1/chat/completions`** is implemented behind **`EXO_ENABLE_OPENAI_COMPAT_GATEWAY`** (see `docs/plans/northbound-v1-gateway.md`).

## 4) Lane A (universal OpenAI-compatible adapter package)

| Item | Status |
|------|--------|
| `exo-adapter-universal` (or equivalent) implementing Lane A behind same `RuntimeAdapter` contract | **Deferred** |
| Owner | Savin I. Razvan |
| As-of | 2026-03-24 |
| Note | Universal **package** spike still deferred; two distinct **`base_url`** registrations are covered in API tests. See [`adapter-strategy.md` §19.4–19.6](adapter-strategy.md#194-three-lane-expansion-model). |

## 5) Certification status (in-repo adapters)

| Adapter package | Version | Conformance tests | External install smoke | Notes |
|-----------------|---------|-------------------|-------------------------|-------|
| `exo-adapter-echo` | 0.1.0 | `tests/packages/test_echo_adapter_conformance.py` | Run `scripts/packages/external_install_smoke.py` before release | Reference deterministic adapter for multi-adapter parity |
| `exo-adapter-openai` | 0.1.0 | `tests/packages/test_openai_adapter_conformance.py` | Run `scripts/packages/external_install_smoke.py` before release | Requires OpenAI SDK deps in env |

**Lane A (two `base_url` configs):** API persistence + registration coverage — `tests/modules/api/test_slice_provider_registration.py::test_post_providers_two_distinct_openai_compatible_base_urls`.

## 6) Certification checklist (per adapter release)

Minimum evidence before claiming **GA** for a **new** provider adapter (aligns with [`adapter-strategy.md` §12](adapter-strategy.md#12-adapter-certification-pipeline)):

1. Conformance: `RuntimeAdapter` async contract + error envelopes.
2. In-repo: `tests/packages/test_*_adapter_conformance.py` (and full `pytest` green).
3. Isolated install: `python scripts/packages/external_install_smoke.py` from a clean intent.
4. Matrix row updated in §1 with version + supported contracts/SDK range.

## Revision

| Date | Change |
|------|--------|
| 2026-03-24 | Initial matrix: package versions, semver, M0 done, Lane A deferred. |
| 2026-03-24 | §5 certification rows (echo/openai); §6 checklist rename; Lane A two-`base_url` test anchor. |

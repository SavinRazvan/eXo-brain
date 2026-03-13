<!--
File: ADAPTER_STRATEGY.md
Path: architecture-goals/ADAPTER_STRATEGY.md
Role: Canonical adapter strategy for provider-neutral packaging, governance boundaries, and monetization-safe extensibility.
Used By:
 - architecture-goals/GOAL.md
 - AGENTS.md
 - docs/plans/tenant-tool-execution-architecture.md
Depends On:
 - packages/exo-brain-core-contracts/*
 - packages/exo-brain-adapter-sdk/*
 - src/runtime/*
 - src/core/*
 - src/policies/*
 - src/api/*
Notes:
 - Keep aligned with API-first Option C.
 - Keep adapter packaging decisions compatible with contract versioning policy.
-->

# Adapter Strategy

## Governance Metadata

- Status: `active`
- Owner: `Savin I. Razvan`
- Version: `1.0.0`
- Last Reviewed: `2026-03-12`
- Review Cadence: `monthly`
- Decision Scope: `Provider adapter ecosystem boundaries, packaging policy, conformance, and rollout strategy.`

Companion strategy docs:
- `architecture-goals/GOAL.md`
- `architecture-goals/CORE.md`
- `architecture-goals/MONETIZATION_STRATEGY.md`
- `architecture-goals/ENTITLEMENT_MATRIX.md`
- `architecture-goals/DEPLOYMENT_MODELS.md`
- `architecture-goals/TRACEABILITY_MATRIX.md`

## 1) Purpose

Define how eXo-brain supports five provider adapters while preserving one non-negotiable rule:

- adapters handle provider transport/runtime behavior,
- core enforces deterministic safety, policy gates, and governance.

This strategy is designed for:
- safe extensibility,
- customer configurability through API,
- monetization through governance and enterprise controls.

---

## 2) Decision Summary

We standardize the platform into three product layers:

1. `core-contracts` (provider-neutral interfaces and envelopes)
2. `adapter-sdk` (adapter developer kit and conformance)
3. `provider adapters` (OpenAI, Google, Anthropic, xAI, Meta)

Customers choose providers and fallbacks, but core remains the trust boundary.

---

## 3) Target Adapter Portfolio

Initial provider set:

- OpenAI
- Google Gemini
- Anthropic
- xAI (Grok)
- Meta Llama endpoints

Recommended package names:

- `exo-adapter-openai`
- `exo-adapter-google-gemini`
- `exo-adapter-anthropic`
- `exo-adapter-xai`
- `exo-adapter-meta-llama`

---

## 4) Repository and Packaging Model

Current baseline already includes:
- `packages/exo-brain-core-contracts`
- `packages/exo-brain-adapter-sdk`
- `packages/exo-adapter-openai`

Target authoring workspace for adapters:

```text
exo_adapters/
  openai/
    pyproject.toml
    src/exo_adapter_openai/
    tests/
  google_gemini/
    pyproject.toml
    src/exo_adapter_google_gemini/
    tests/
  anthropic/
    pyproject.toml
    src/exo_adapter_anthropic/
    tests/
  xai/
    pyproject.toml
    src/exo_adapter_xai/
    tests/
  meta_llama/
    pyproject.toml
    src/exo_adapter_meta_llama/
    tests/
```

Publishing principle:
- package names remain `exo-adapter-*`,
- source workspace can be `exo_adapters/*`,
- each adapter is independently installable.

---

## 5) Standard Adapter Internal Structure

Each adapter should expose a consistent internal layout:

```text
src/exo_adapter_<provider>/
  __init__.py
  runtime.py               # RuntimeAdapter implementation
  capabilities.py          # Capability map and health descriptors
  sessions.py              # Session lifecycle and provider session handles
  turns.py                 # Streaming/event translation for run_turn
  tool_wiring.py           # Provider tool-call mapping to core envelopes
  errors.py                # Error normalization to contract format
  settings.py              # Provider-specific config schema
  load.py                  # load_adapter() factory
```

Optional modules when provider needs them:
- `agents.py`
- `workflows.py`
- `completions.py`

Rule:
- optional modules can exist, but they cannot bypass runtime contract and core governance path.

---

## 6) Contract Boundary (Must Stay Stable)

Adapter runtime contract surface:

- `start_session()`
- `run_turn()`
- `submit_tool_results()`
- `get_capabilities()`
- `healthcheck()`

All adapter outputs must normalize to core contract envelopes (`RuntimeEvent`, `ToolResult`, errors).

No adapter may introduce side-effect execution paths that skip:
- policy pre-check,
- deterministic tool execution when required,
- policy post-check,
- audit instrumentation.

---

## 7) Core vs Adapter Responsibilities

## Core owns

- policy decisions (`before_tool_call`, `after_tool_call`)
- risk gate enforcement
- deterministic execution mode switching
- tenancy, quota, fairness, and admission controls
- audit chain and verification
- fallback orchestration policy

## Adapter owns

- provider SDK integration
- request/response streaming translation
- provider capability declaration
- provider health probing
- provider-specific retries/timeouts within contract constraints

If ownership is unclear, default ownership goes to core.

---

## 8) Customer-Facing Configuration Model

Customers configure through API (not by patching core code):

- provider registration and selection,
- ordered fallback chains,
- agent routing and fallback policies,
- risk-mode enforcement preferences,
- per-tenant policy overlays,
- quotas/rate/fairness limits,
- audit queries and export/verify workflows.

Adapter-specific settings are accepted via schema-bound provider metadata.

---

## 9) Fallback Strategy Model

Fallback must be policy and capability aware, not provider-name hardcoded.

Decision order:

1. apply policy constraints (deny/escalate/deterministic enforce),
2. check adapter health and capability map,
3. select primary provider,
4. fail over through ordered fallback list,
5. preserve correlation and audit continuity across failover transitions.

Required behavior:
- deterministic mode requirements survive failover,
- tool execution safety level cannot degrade on fallback.

---

## 10) Security and Governance Rules

Hard rules:

1. No provider SDK imports in core layers.
2. No direct tool side effects from adapter path for risky/state-changing calls.
3. No secrets in logs; use redacted structured logging.
4. Every side-effect path must emit policy and audit evidence.
5. Every adapter version must pass conformance and safety gates before release.

Operational controls:
- per-adapter kill switch,
- per-tenant adapter allowlist,
- emergency fallback profile,
- version pinning and rollback.

---

## 11) Monetization-Aligned Feature Model

Monetization focus is governance and reliability, not model API pass-through.

## Foundation (base)

- provider-neutral orchestration
- basic adapter runtime support
- baseline deterministic and policy controls

## Pro

- advanced policy templates and risk profiles
- richer fallback strategies and route controls
- enhanced operational telemetry and diagnostics

## Enterprise

- signed audit evidence workflows
- stronger tenancy governance and fairness controls
- compliance-ready export/verification bundles
- SLO-gated release and operational playbooks

Adapters are necessary for adoption; governance features drive premium value.

---

## 12) Adapter Certification Pipeline

Every adapter release must pass:

1. Contract conformance tests (`RuntimeAdapter` methods and async behavior)
2. Capability map validity checks
3. Event shape and streaming translation tests
4. Deterministic path non-bypass tests
5. Policy hook invocation verification
6. Error normalization tests (provider errors to standard envelopes)
7. Retry/timeout/cancellation behavior tests
8. Security checks (secret handling, no unsafe logging)
9. Performance smoke checks (latency and timeout ratios)
10. Compatibility checks against supported core-contract versions

Release block:
- fail any P0 safety or contract gate -> do not publish.

---

## 13) Adapter Versioning Policy

- `core-contracts` is semver-governed and backward compatibility is explicit.
- `adapter-sdk` tracks compatible contract ranges.
- each adapter declares tested compatibility matrix:
  - core-contract version range,
  - adapter-sdk version range,
  - provider SDK version range.

Publishing rule:
- never publish adapter versions that require undocumented core internals.

---

## 14) Migration Requirement (Current Gap)

Current adapter packaging must be completed to full portability:

- remove monorepo-only `src.*` imports from adapter packages,
- make provider adapters depend only on published contracts/sdk packages,
- validate install/use from an external clean project.

Definition of done for portability:
- `pip install exo-adapter-<provider>` works outside this repo,
- adapter passes conformance without monorepo path hacks.

---

## 15) Implementation Slices for 5 Adapters

## Slice A - Contract freeze and packaging baseline

- lock v1 contract interface and error envelope requirements,
- finalize `core-contracts` and `adapter-sdk` compatibility policy,
- define adapter template repo layout.

## Slice B - OpenAI extraction completion

- remove remaining monorepo import dependencies,
- pass clean external-install conformance path,
- publish as reference adapter.

## Slice C - Google Gemini + Anthropic

- implement two additional adapters from same template,
- validate streaming/tool translation parity with OpenAI baseline,
- run cross-adapter fallback tests.

## Slice D - xAI + Meta

- add last two adapters,
- verify capability matrix completeness,
- validate behavior under mixed-fallback chains.

## Slice E - Certification and release automation

- automate adapter certification gates in CI,
- add release evidence artifacts per adapter version,
- publish adapter compatibility matrix docs.

---

## 16) Non-Negotiable Acceptance Criteria

Platform-level:

- customers can choose provider and fallback chain entirely through API,
- policy and deterministic enforcement remain active regardless of provider,
- audit trail remains complete during primary and fallback flows.

Adapter-level:

- each adapter can run standalone outside monorepo,
- each adapter passes conformance and security gates,
- each adapter declares supported contract/sdk/provider version matrix.

Business-level:

- paid feature boundaries are enforceable by entitlement/config gates,
- premium value remains in governance/reliability layers, not connector lock-in.

---

## 17) Open Questions to Resolve Before Full Rollout

1. Do we publish adapters from one monorepo pipeline or per-adapter release pipelines?
2. What minimum SLA profile do we guarantee per certified adapter?
3. Which governance features are feature-flagged for Pro vs Enterprise?
4. Do we support customer-provided private adapters under signed certification only?
5. What is the deprecation policy for old provider SDK major versions?

---

## 18) Alignment Check (Use Before Merging Adapter Changes)

- Does this change preserve provider-neutral core boundaries?
- Does it keep policy/deterministic/audit non-bypassable?
- Can customer control it through API and settings schemas?
- Is portability improved (or at least not regressed)?
- Does it strengthen monetizable governance value?
- Is traceability updated in `architecture-goals/TRACEABILITY_MATRIX.md`?

If any answer is "no", redesign before merge.

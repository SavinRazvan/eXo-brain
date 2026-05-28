<!--
File: adapter-installation.md
Path: docs/operations/adapter-installation.md
Role: Operator guide for installing published adapter wheels and registering providers.
Used By:
 - Foundation-tier adopters and self-hosted operators
Depends On:
 - requirements.txt, requirements-adapters.txt
 - docs/strategy/foundation-tier-adoption-checklist.md
 - SavinRazvan/eXo_adapters (PyPI)
Notes:
 - Control-plane operator docs live in eXo-brain; adapter repo keeps maintainer pointers only.
-->

# Installing runtime adapters (operators)

## What to install

| Install surface | Contents |
|-----------------|----------|
| `pip install -r requirements.txt` | Control plane + **`exo-brain-core-contracts==0.1.1`** (no provider SDKs) |
| `pip install -r requirements-adapters.txt` | **`exo-brain-adapter-sdk`**, **`exo-adapter-openai`**, **`exo-adapter-echo`** at **0.1.1** |

Development / CI without PyPI: `bash scripts/dev/install_adapter_dependencies.sh` (PyPI first, editable fallback from `packages/repo_for_pipy/`).

Docker images run the same script during build.

## Canonical `adapter_class_ref` values

| Provider kind | `adapter_class_ref` |
|---------------|---------------------|
| OpenAI Agents SDK | `exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter` |
| Echo (deterministic, no API key) | `exo_adapter_echo.runtime.EchoRuntimeAdapter` |

Register via `POST /providers` (see [`foundation-tier-adoption-checklist.md`](../strategy/foundation-tier-adoption-checklist.md)) or seed in provider registry config.

## Environment

- **OpenAI:** set `OPENAI_API_KEY` (or the env var named in provider `api_key_env_var`).
- **Echo:** no provider API key; use for CI, smoke tests, and multi-adapter parity.

## Version pairing

Adapter distributions **0.1.1** are tested with eXo-brain **v0.1.0+**. See [`adapter-compatibility-matrix.md`](../strategy/adapter-compatibility-matrix.md) before bumping pins.

## Maintainer releases

Lockstep tag → four PyPI wheels → bump `requirements.txt` / `requirements-adapters.txt` in eXo-brain. See [eXo_adapters `RELEASE.md`](https://github.com/SavinRazvan/eXo_adapters/blob/main/RELEASE.md) and `docs/versioning-and-releases.md` in that repo.

## Repo layout

You do **not** need a separate GitHub repo for contracts — see [`adapter-repos-and-pypi.md`](adapter-repos-and-pypi.md).

## Live OpenAI smoke test

```bash
export OPENAI_API_KEY="..."
export EXO_RUN_LIVE_OPENAI=1
pytest tests/modules/runtime/test_openai_live_integration.py -q
```

## OpenAI adapter behavior (0.1.1+)

- **Governed tools:** `FunctionTool` bodies delegate to eXo-brain’s executor (no duplicate `TOOL_INTENT` from the Agents stream when registry + executor are wired).
- **After orchestrator tool execution:** `submit_tool_results` calls the model again with formatted tool results when `OPENAI_API_KEY` is set.
- **`planned_tool_call`:** still emits `tool_intent` for deterministic orchestration.

Details: [packages-reference](https://github.com/SavinRazvan/eXo_adapters/blob/main/docs/packages-reference.md), [`submit-tool-results-orchestrator-only.md`](../decisions/submit-tool-results-orchestrator-only.md) (updated for continuation).

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
| `pip install -r requirements.txt` | Control plane + all four adapter distributions (lockstep pin in file) |
| `pip install -r requirements-adapters.txt` | All four adapter distributions only (same pins as above) |

Development / CI / Docker: `bash scripts/dev/install_adapter_dependencies.sh` (PyPI via `requirements.txt`).

**PyPI only** — eXo-brain does not auto-install from a sibling `eXo_adapters` checkout. Adapter
maintainers who need editable installs must set `EXO_ADAPTERS_ROOT` explicitly and run
`scripts/dev/install_requirements_with_sibling_exo_adapters.sh` (opt-in, not used in CI).

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

Adapter distributions are tested with eXo-brain **v0.1.0+**. See [`adapter-compatibility-matrix.md`](../strategy/adapter-compatibility-matrix.md) before bumping pins.

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

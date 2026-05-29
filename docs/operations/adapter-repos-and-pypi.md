<!--
File: adapter-repos-and-pypi.md
Path: docs/operations/adapter-repos-and-pypi.md
Role: Clarify GitHub/PyPI layout — one adapters repo, four wheels; how eXo-brain consumes them.
Used By:
 - Operators and maintainers wiring pip install
Depends On:
 - packages/eXo_adapters (in-tree copy of SavinRazvan/eXo_adapters)
Notes:
 - You do not need a separate GitHub repo per package name.
-->

# Adapter repos and PyPI — what you need

## Short answer

| Question | Answer |
|----------|--------|
| Separate repo for **contracts**? | **No.** `exo-brain-core-contracts` is one of **four wheels** in the **same** adapters repo. |
| Separate repo for **SDK**? | **No** (unless you keep a legacy fork). Publish **`exo-brain-adapter-sdk`** from **`SavinRazvan/eXo_adapters`** with the other three packages. |
| What does **eXo-brain** need? | This repo only — install wheels via pip; no vendored adapter source required after PyPI publish. |

## Repository map

```text
SavinRazvan/eXo-brain          → control plane (orchestrator, API, policy, tools)
SavinRazvan/eXo_adapters       → four PyPI packages (in eXo-brain dev: packages/eXo_adapters/packages/)
```

**Four PyPI distribution names (lockstep 0.1.1):**

1. `exo-brain-core-contracts`
2. `exo-brain-adapter-sdk`
3. `exo-adapter-echo`
4. `exo-adapter-openai`

## Install commands (eXo-brain environment)

**Minimum (control plane + shared types):**

```bash
pip install -r requirements.txt
# includes exo-brain-core-contracts==0.1.1
```

**Full runtime (OpenAI + echo adapters):**

```bash
pip install -r requirements.txt
pip install -r requirements-adapters.txt
```

Equivalent one-liner after publish:

```bash
pip install exo-brain-core-contracts==0.1.1 \
  exo-brain-adapter-sdk==0.1.1 \
  exo-adapter-echo==0.1.1 \
  exo-adapter-openai==0.1.1
```

Or from eXo-brain root:

```bash
bash scripts/dev/install_adapter_dependencies.sh
```

## Register in eXo-brain

| Provider | `adapter_class_ref` |
|----------|---------------------|
| OpenAI | `exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter` |
| Echo | `exo_adapter_echo.runtime.EchoRuntimeAdapter` |

Set `OPENAI_API_KEY` for live OpenAI turns.

## Live verification (you have an API key)

```bash
export OPENAI_API_KEY="sk-..."
export EXO_RUN_LIVE_OPENAI=1
pytest tests/modules/runtime/test_openai_live_integration.py -q
```

## If you already have `exo-brain-adapter-sdk` as its own repo

Merge or mirror it into **`eXo_adapters`** under `packages/exo-brain-adapter-sdk/`. PyPI expects the **distribution name** `exo-brain-adapter-sdk`, not a second control-plane repo. eXo-brain should **not** publish contracts from the control-plane repo long term.

## Publish checklist (maintainer)

1. Push `packages/repo_for_pipy` → `SavinRazvan/eXo_adapters`
2. Tag `v0.1.1` → GitHub `release.yml` → PyPI (Trusted Publishing)
3. Confirm: `pip install exo-adapter-openai==0.1.1` in a **clean** venv
4. Run eXo-brain: `bash scripts/dev/install_adapter_dependencies.sh` and targeted pytest

See also [`adapter-installation.md`](adapter-installation.md).

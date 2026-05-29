<!--
File: adapter-repos-and-pypi.md
Path: docs/operations/adapter-repos-and-pypi.md
Role: Clarify GitHub/PyPI layout — one adapters repo, four wheels; how eXo-brain consumes them.
Used By:
 - Operators and maintainers wiring pip install
Depends On:
 - SavinRazvan/eXo_adapters (GitHub + PyPI)
Notes:
 - eXo-brain does not vend adapter source; install wheels via pip only.
-->

# Adapter repos and PyPI — what you need

## Short answer

| Question | Answer |
|----------|--------|
| Separate repo for **contracts**? | **No.** `exo-brain-core-contracts` is one of **four wheels** in **`SavinRazvan/eXo_adapters`**. |
| Separate repo for **SDK**? | **No.** Publish **`exo-brain-adapter-sdk`** from the same adapters repo. |
| What does **eXo-brain** need? | `pip install -r requirements.txt` — four lockstep pins, no local `packages/` tree. |

## Repository map

```text
SavinRazvan/eXo-brain     → control plane (orchestrator, API, policy, tools)
SavinRazvan/eXo_adapters  → four PyPI packages (authoring, tests, releases)
```

**Four PyPI distribution names (lockstep; see `requirements.txt` for current pin):**

1. `exo-brain-core-contracts`
2. `exo-brain-adapter-sdk`
3. `exo-adapter-echo`
4. `exo-adapter-openai`

## Install commands (eXo-brain environment)

**Full dev / CI / Docker:**

```bash
pip install -r requirements.txt
# or
bash scripts/dev/install_adapter_dependencies.sh
```

**Adapter wheels only** (same four pins as `requirements.txt`):

```bash
pip install -r requirements-adapters.txt
```

**Adapter development** (editable installs — opt-in, explicit path only):

```bash
export EXO_ADAPTERS_ROOT=/absolute/path/to/eXo_adapters
bash scripts/dev/install_requirements_with_sibling_exo_adapters.sh
```

Do **not** rely on `../eXo_adapters`; eXo-brain CI and default install use **PyPI only**.

Operator details: [adapter-installation.md](adapter-installation.md).

## Maintainer releases

1. Change adapter source in **`SavinRazvan/eXo_adapters`**
2. Tag lockstep release → publish four wheels to PyPI
3. Bump pins in eXo-brain `requirements.txt` / `requirements-adapters.txt`
4. Run `python scripts/packages/external_install_smoke.py` and full pytest

See [eXo_adapters RELEASE.md](https://github.com/SavinRazvan/eXo_adapters/blob/main/RELEASE.md).

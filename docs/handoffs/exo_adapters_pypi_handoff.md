<!--
File: exo_adapters_pypi_handoff.md
Path: docs/handoffs/exo_adapters_pypi_handoff.md
Role: End-to-end handoff for creating the public eXo_adapters repo, publishing adapter packages to PyPI, and wiring eXo-brain to consume them.
Used By:
 - Maintainer spinning out adapters into a separate public project
 - Implementation agent responsible for packaging + releases
Depends On:
 - docs/plans/adapter-packages-extraction-handoff.md
 - scripts/packages/external_install_smoke.py
 - scripts/architecture/scan_forbidden_imports.py
 - tests/adapter_package_paths.py
 - tests/packages/test_openai_adapter_conformance.py
 - tests/packages/test_echo_adapter_conformance.py
 - src/runtime/adapter_factory.py
Notes:
 - This is written as an agent mission playbook: acceptance criteria, exact steps, and guardrails.
-->

# Handoff: publish **eXo_adapters** (GitHub + PyPI) and connect to **eXo-brain**

## Mission (what you are responsible for)

Create a new public GitHub repository (**`eXo_adapters`**) that contains the portable adapter packages and publish them to PyPI in a way that:

- eXo-brain can consume the packages via normal `pip install ...` (no local path hacks).
- Provider SDK imports remain **behind adapter boundaries** (adapter wall).
- Adapter packages remain **portable**: they must not import monorepo `src.*` modules.
- A clean venv can install and import the full stack and run the smoke assertions.

This handoff assumes the control-plane repo (`eXo-brain`) remains the **governed execution control plane** and the adapters move out as a separate project.

## What must end up on PyPI (distributions)

The new repo publishes these **four** packages (distribution names must remain exactly these, because code/tests/documentation already assume them):

- `exo-brain-core-contracts`
- `exo-brain-adapter-sdk`
- `exo-adapter-echo`
- `exo-adapter-openai`

Source-of-truth inventory and responsibilities are in:
- `docs/plans/adapter-packages-extraction-handoff.md`

## Acceptance criteria (definition of done)

### A. New repo / code portability

- A public repo exists: `SavinRazvan/eXo_adapters` (or equivalent target org/name).
- Repo contains multi-package layout under `packages/` (see layout section below).
- Adapter packages do **not** import `src` or `src.*` anywhere (portability rule).
- `python scripts/external_install_smoke.py` (in the new repo) passes on a clean machine/venv.

### B. PyPI publishing

- All four distributions are published to PyPI.
- Versions are consistent and documented.
- Release process is repeatable (CI or scripted).

### C. eXo-brain integration

- eXo-brain installs from PyPI, not local `packages/eXo_adapters/...` paths.
- `src/runtime/adapter_factory.py` successfully loads adapter class refs that point to the published modules:
  - `exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter`
  - `exo_adapter_echo.runtime.EchoRuntimeAdapter`
- eXo-brain CI/test gates remain green (or are updated intentionally with justification).

## Guardrails (do not violate)

- **No provider SDK imports outside adapters**: the control plane must not import `openai`, etc. This is enforced by `scripts/architecture/scan_forbidden_imports.py` in eXo-brain.
- **No monorepo import leakage inside adapters**: adapter packages must not import `src.*`. Conformance tests enforce this.
- Keep compatibility between:
  - `exo_brain_core_contracts.runtime_adapter.RuntimeAdapter` (published)
  - `src/runtime/runtime_adapter.py` / `src/schemas/tool_io.py` / `src/schemas/events.py` (control plane re-exports)

## Target repository layout (recommended)

Use a **single repo, multiple distributions**:

```text
eXo_adapters/
  README.md
  LICENSE
  NOTICE
  packages/
    exo-brain-core-contracts/
      pyproject.toml
      src/exo_brain_core_contracts/...
    exo-brain-adapter-sdk/
      pyproject.toml
      src/exo_brain_adapter_sdk/...
    exo-adapter-echo/
      pyproject.toml
      src/exo_adapter_echo/...
    exo-adapter-openai/
      pyproject.toml
      src/exo_adapter_openai/...
  scripts/
    external_install_smoke.py
  tests/
    test_openai_adapter_conformance.py
    test_echo_adapter_conformance.py
    test_core_contracts_imports.py   (optional)
  .github/workflows/
    ci.yml
    release.yml (optional)
```

Notes:
- `scripts/external_install_smoke.py` should be migrated from eXo-brain’s `scripts/packages/external_install_smoke.py`, with path probes simplified because the packages are native to this repo.
- Keep tests lightweight and network-free; conformance tests are already designed to not require API keys.

## Step-by-step execution plan

### 1) Create the new GitHub repo

- Create repo (public): `eXo_adapters`
- Add baseline community files as needed (license, contributing, security) — keep consistent with eXo-brain’s OSS posture.

### 2) Copy sources from eXo-brain into eXo_adapters

In eXo-brain, the portable sources may appear in one of these local workspaces:
- `eXo_adapters/packages/` (sibling checkout)
- `packages/eXo_adapters/packages/` (local clone sitting inside eXo-brain)
- `moving_to_adapters_project/packages/` (staging)

The **canonical** inventory to move is:
- `docs/plans/adapter-packages-extraction-handoff.md` (§2)

Do **not** copy:
- `*.egg-info/` directories (build artifacts)
- `.local/` / `.venv/` / any secrets

### 3) Ensure each package is independently buildable

Each distribution must have:
- `pyproject.toml` with correct `name`, `version`, `requires-python`, and dependencies
- `src/<import_package>/...` layout
- working `pip install -e packages/<pkg>`

Dependency edges (must be correct):
- `exo-brain-adapter-sdk` depends on `exo-brain-core-contracts`
- `exo-adapter-echo` depends on `exo-brain-core-contracts`
- `exo-adapter-openai` depends on:
  - `exo-brain-core-contracts`
  - `openai`
  - `openai-agents`

### 4) Add portability/conformance tests into eXo_adapters

Port/mirror the conformance tests from eXo-brain:
- `tests/packages/test_openai_adapter_conformance.py`
- `tests/packages/test_echo_adapter_conformance.py`

But adjust path handling:
- In eXo_adapters, tests should import from **installed packages** (or editable installs), not by hacking sys.path to a monorepo candidate.

Minimum tests that must pass in eXo_adapters CI:
- Import each package.
- Ensure adapter modules do not import `src.*`.
- Ensure `load_adapter(...)` factories work.
- Ensure `run_turn(...)` yields expected event types (conformance smoke).

### 5) Create `scripts/external_install_smoke.py` in eXo_adapters

Use eXo-brain’s script as the starting point:
- Source: `scripts/packages/external_install_smoke.py`

In the new repo:
- Remove probing logic for “optional workspace”; your workspace is always `packages/`.
- Keep the same checks:
  - imports
  - module origin not `src.*`
  - `assert_runtime_adapter_contract`
  - `run_turn` event shape for OpenAI adapter and Echo adapter

This script becomes the “single command” that proves a clean venv can install everything.

### 6) Set up PyPI publishing (recommended approach)

Recommended: **PyPI Trusted Publisher** via GitHub Actions (no long-lived API tokens).

Deliverables in eXo_adapters:
- CI workflow that builds wheels/sdists for all packages.
- Release workflow that publishes per-package artifacts.

Key decision: **release coupling**

Choose one (document it in the repo README):

- **Option 1: lockstep versions** (simpler)
  - all four packages share the same version number (e.g. `0.2.0`)
  - one tag publishes all four
  - easier compatibility story
- **Option 2: independent versions**
  - contracts bump implies coordinated bumps
  - more flexibility but more maintenance

Given the adapter wall + compatibility needs, lockstep is usually the safer default for a solo-maintainer project.

### 7) Wire eXo-brain to use PyPI (remove local path dependency)

In eXo-brain, update `requirements.txt`:

- Replace the local editable contracts line:
  - currently: `-e ./packages/eXo_adapters/packages/exo-brain-core-contracts`
- With PyPI pins/ranges:
  - `exo-brain-core-contracts==X.Y.Z` (or `>=X.Y.Z`)

Then decide how to surface adapters:

- **Recommended**: make adapters optional extras (so the control plane installs without provider deps):
  - base requirements: control plane + contracts
  - optional: `exo-adapter-openai`, `exo-adapter-echo`

If eXo-brain today expects OpenAI adapter by default, you can either:
- keep a “default adapter” extra, or
- keep in-tree fallback adapter until PyPI path is proven stable, then remove the fallback.

### 8) Update eXo-brain CI to cover dependency bumps properly

Today, `architecture-fitness.yml` runs on `src/**`, `tests/**`, `packages/**`, etc.

To avoid dependency PRs slipping through with only CodeQL checks, update eXo-brain CI so that:
- `requirements.txt` changes trigger the full suite (or at least pytest + architecture scans).

Concretely:
- add `requirements.txt` to `.github/workflows/architecture-fitness.yml` `paths:` trigger.

### 9) Decide what to do with `tests/packages/*` in eXo-brain

Those tests currently skip unless a local adapter workspace exists.

After moving adapters out, eXo-brain has three sensible choices:

- **Choice A (recommended):** convert `tests/packages/*` into “installed package” tests
  - install `exo-adapter-echo` and `exo-adapter-openai` in CI (via extras)
  - run conformance tests against installed packages
- **Choice B:** keep them as optional local-only tests (documented)
  - fine if you don’t want provider deps in CI
- **Choice C:** move them entirely to eXo_adapters and delete from eXo-brain
  - then keep only a minimal integration smoke in eXo-brain

Pick one and update docs accordingly.

## How eXo-brain loads adapters (what must remain true)

The control plane loads adapters by dotted class reference. The published adapters must expose stable import paths, e.g.:

- `exo_adapter_openai.runtime.OpenAIAgentsRuntimeAdapter`
- `exo_adapter_echo.runtime.EchoRuntimeAdapter`

The load path is resolved in:
- `src/runtime/adapter_factory.py`

The adapter wall rule is enforced by:
- `scripts/architecture/scan_forbidden_imports.py`

## Checklist (copy/paste for the implementing agent)

### Repo setup
- [ ] Create new public repo `eXo_adapters`.
- [ ] Add `packages/` with the four package trees.
- [ ] Ensure each package has `pyproject.toml` and `src/` package layout.
- [ ] Ensure no `src.*` imports exist inside adapters.

### Test + smoke
- [ ] Add unit/conformance tests in `eXo_adapters/tests/`.
- [ ] Add `scripts/external_install_smoke.py` and run it locally.
- [ ] Add GitHub Actions CI: run pytest + smoke script.

### Publish
- [ ] Choose versioning model (lockstep vs independent).
- [ ] Configure Trusted Publishing to PyPI.
- [ ] Publish all four distributions.

### Wire eXo-brain
- [ ] Replace local `-e ./packages/eXo_adapters/...` in `requirements.txt` with PyPI dependency.
- [ ] Decide whether adapters are default deps or optional extras.
- [ ] Update CI triggers to include `requirements.txt`.
- [ ] Decide fate of `tests/packages/*` in eXo-brain (A/B/C above) and implement.

## Notes on why `packages/eXo_adapters/**` is ignored in eXo-brain

In eXo-brain, `packages/eXo_adapters/` may exist as a local sibling clone for development, but it must not be accidentally committed/published as part of the control-plane repo. Only the small `exo-brain-core-contracts` subset was temporarily vendored for CI. Once PyPI publishing is in place, eXo-brain should stop vendoring this subtree entirely.


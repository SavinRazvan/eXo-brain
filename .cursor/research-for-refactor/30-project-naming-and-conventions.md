# Project Naming and Conventions (eXo-brain)

## Purpose
This document defines naming conventions for brand, repository, Python package, modules, and symbols so implementation stays standards-compliant while preserving the project identity.

## Canonical Name Mapping
- Brand/display name: `eXo-brain`
- Repository name: `exo-brain`
- Python package/import root: `exo_brain`
- PyPI distribution name: `exo-brain`
- Docker image name (recommended): `exo-brain`

## Why This Mapping
- Keep the stylized brand (`eXo-brain`) only for human-facing surfaces.
- Use lowercase kebab-case for repo/distribution identifiers.
- Use snake_case for Python imports and module paths.
- Avoid mixed casing in technical identifiers to reduce tooling friction.

## Naming Rules (Repository-Wide)

### Files and Paths
- Use `snake_case` for Python files (`task_graph.py`, `runtime_adapter.py`).
- Use lowercase kebab-case for non-Python doc names when needed.
- Keep package directories lowercase (`core`, `runtime`, `agents`, `tools`).

### Python Symbols
- Classes: `PascalCase` (`AgentOrchestrator`, `PolicyMiddleware`).
- Functions/methods/variables: `snake_case`.
- Constants and environment variables: `UPPER_SNAKE_CASE`.
- Protocols/interfaces: suffix with role when useful (`RuntimeAdapter`, `SessionStore`).

### Config and Env Keys
- Prefix project-wide keys with `EXO_BRAIN_` when appropriate.
- Provider-specific keys may keep provider prefixes (`OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`).
- Feature flags should be explicit and boolean-like (`EXO_BRAIN_ENABLE_MCP=true`).

## Ready-to-Use Section for README.md

```md
## Naming Conventions

To keep branding clear and implementation standards-compliant, this project uses:

- **Brand/display name:** `eXo-brain`
- **Repository name:** `exo-brain`
- **Python package/import root:** `exo_brain`
- **PyPI distribution name:** `exo-brain`

Code style conventions:
- Classes use `PascalCase`
- Functions/variables/files use `snake_case`
- Constants/env vars use `UPPER_SNAKE_CASE`
```

## Ready-to-Use Section for Architecture Docs

```md
## Naming and Identifier Standards

This architecture uses a split identity model:
- Human-facing brand: `eXo-brain`
- Technical identifiers: lowercase standard forms

Canonical mappings:
- Repo: `exo-brain`
- Python package: `exo_brain`
- Distribution: `exo-brain`

Module and symbol conventions:
- Module files: `snake_case` (example: `handoff_router.py`)
- Classes: `PascalCase` (example: `HandoffRouter`)
- Contracts/interfaces: explicit adapter/store naming (example: `RuntimeAdapter`, `CheckpointStore`)
```

## Monorepo or Multi-Repo Naming Pattern (Optional)
- `exo-brain` (root or umbrella)
- `exo-brain-core`
- `exo-brain-sdk`
- `exo-brain-agents`
- `exo-brain-examples`

## Guardrails
- Do not use stylized casing (`eXo`) in package/module/import names.
- Do not use hyphens in Python import paths.
- Do not rename package root after public release without a migration alias plan.

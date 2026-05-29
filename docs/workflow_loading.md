<!--
File: workflow_loading.md
Path: docs/workflow_loading.md
Role: Workflow definition loading, validation, and versioned registry semantics.
Used By:
 - docs/README.md
 - docs/runtime_contracts.md
Depends On:
 - src/core/workflow_loader.py
 - src/schemas/workflow_schema.py
 - tests/modules/core/test_workflow_loader.py
Notes:
 - Loader is tested; not yet wired into background_runtime or public API paths (Used By: tests + module contracts).
 - Last reviewed: 2026-05-29
-->

# Workflow loading

**Status:** active (library); **integration:** pre-API / orchestration hook-up  
**Owner:** Savin I. Razvan

## Scope

`WorkflowLoader` in `src/core/workflow_loader.py` validates and registers **versioned** workflow definitions before orchestration consumes them. Schema types live in `src/schemas/workflow_schema.py`.

## Responsibilities

- Load workflow definitions from local **JSON** or **YAML** (`.yaml` / `.yml`) files.
- Validate schema/version compatibility via `WorkflowDefinition` parsing.
- Register workflows by `(workflow_id, version)` in an in-memory registry.
- Return structured `WorkflowLoadError` with stable `code` fields (fail closed).

### Public API (loader)

| Method | Behavior |
|---|---|
| `load_workflow(source, replace_existing=False)` | Parse file, register handle |
| `reload_workflow(source)` | `replace_existing=True` |
| `get_workflow(workflow_id, version)` | Lookup or `WORKFLOW_NOT_FOUND` |
| `list_workflows()` | Sorted handles |

### Example error codes

`WORKFLOW_SOURCE_NOT_FOUND`, `WORKFLOW_ALREADY_REGISTERED`, `WORKFLOW_EXTENSION_UNSUPPORTED`, `WORKFLOW_JSON_INVALID`, `WORKFLOW_PAYLOAD_TYPE_INVALID`, schema errors from `WorkflowSchemaError`.

## Runtime integration status (factual)

| Consumer | Status |
|---|---|
| `tests/modules/core/test_workflow_loader.py` | **Covered** |
| `tests/modules/core/test_workflow_loader_integration.py` | **Covered** |
| `src/core/background_runtime.py` / task graph | **Not wired** — loader module header still lists Used By as TBD until orchestration imports it |
| Public HTTP API | **No** dedicated workflow upload route in current routers |

Multi-step **workflow** execution ownership remains in `src/core/*` (scheduler, task graph) per [runtime_contracts.md](runtime_contracts.md). When wiring the loader, keep provider-neutral boundaries: workflows coordinate steps; runtime adapters execute individual model/tool turns.

## Related

- [docs/modules/core.md](modules/core.md)
- [runtime_contracts.md](runtime_contracts.md) — workflow vs chat/agents ownership table
- [tenant-tool-execution-architecture.md](plans/tenant-tool-execution-architecture.md)

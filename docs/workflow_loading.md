# Workflow Loading

## Scope
The workflow loader validates and registers versioned workflow definitions before execution.

## Responsibilities
- Load workflow definitions from local JSON/YAML sources.
- Validate schema/version compatibility.
- Register workflows by `workflow_id` and `version`.
- Return structured validation errors for invalid schemas.

## Runtime behavior
- Loaded workflows are consumed by background runtime/scheduler paths.
- Version mismatches fail closed with auditable error envelopes.

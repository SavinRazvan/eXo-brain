# Plugin Lifecycle

## Supported lifecycle operations
- `load_plugin`
- `unload_plugin`
- `reload_plugin`
- `validate_compatibility`
- `list_plugins`

## Safety requirements
- Block unload when non-idempotent active work exists.
- Validate compatibility before activation.
- Record lifecycle operations in structured logs and audit stream.
- Enforce decorator ordering so security hooks cannot be bypassed.

## Extension model
- Plugins contribute capabilities, descriptors, and optional hooks.
- Core orchestrator remains decoupled from plugin internals.

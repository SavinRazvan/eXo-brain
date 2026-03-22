<!--
File: README.md
Path: docs/templates/local-workspace/README.md
Role: Explains versioned templates copied into gitignored `.local/agents-control-center/`.
Used By:
 - docs/operations/local-workspace-layout.md
Depends On:
 - scripts/dev/migrate_local_workspace_layout.py
Notes:
 - After editing templates, run the migration script with `--dry-run`, then apply on your machine.
-->

# Local workspace templates

Copy (or let `scripts/dev/migrate_local_workspace_layout.py` copy) into `.local/`:

| Template | Target |
|----------|--------|
| `pages.json` | `.local/agents-control-center/config/pages.json` |
| `implementation-control-center.html` | `.local/agents-control-center/dashboards/implementation-control-center.html` |

Paths inside `pages.json` are relative to the dashboard HTML file location (`dashboards/`).

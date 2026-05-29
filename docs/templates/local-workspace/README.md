<!--
File: README.md
Path: docs/templates/local-workspace/README.md
Role: Explains versioned templates copied into gitignored `.local/agents-control-center/`.
Used By:
 - docs/operations/local-workspace-layout.md
Depends On:
 - scripts/dev/migrate_local_workspace_layout.py
 - docs/plans/control-plane-product-alignment-plan.md
 - docs/strategy/governed-execution-positioning.md
Notes:
 - After editing templates, run the migration script with `--dry-run`, then apply on your machine.
 - `pages.json` includes durable **strategy** and **control plane plan** tabs (paths under `docs/`); merge into your live `.local/.../pages.json` if you already customized tabs.
-->

# Local workspace templates

Copy (or let `scripts/dev/migrate_local_workspace_layout.py` copy) into `.local/`:

| Template | Target |
|----------|--------|
| `index.html` | `.local/agents-control-center/dashboards/index.html` (landing — open first) |
| `pages.json` | `.local/agents-control-center/config/pages.json` |
| `implementation-control-center.html` | `.local/agents-control-center/dashboards/implementation-control-center.html` |
| `local-shell.css` | `.local/agents-control-center/dashboards/local-shell.css` (shared look; **overwritten** on migrate) |
| `site-nav.js` | `.local/agents-control-center/dashboards/site-nav.js` (sticky **Navigator** bar; **overwritten** on migrate) |
| `audits/module-audit.html` | `.local/agents-control-center/audits/module-audit.html` (stub until an audit export overwrites it) |

**HTML page count (default): 3** — `dashboards/index.html`, `dashboards/implementation-control-center.html`, `audits/module-audit.html`. The shared **`site-nav.js`** adds the same three **button-style links** at the top of each page (`data-local-site` / `data-local-active` on `<html>` select the current page). Add a fourth page by extending `site-nav.js` and adding `data-local-active` values on the new shell.

Paths inside `pages.json` are relative to the dashboard HTML file location (`dashboards/`).

Do not point `pages.json` tab `file` entries at HTML audit files (tabs expect Markdown).

**Typo guard:** if you see requests ending in `module-audit.htmlmodule-audit.html`, check `pages.json` for a duplicated filename in the `file` field.

## Product vocabulary (for agents using this dashboard)

When implementing or documenting integrations, use the same terms as `README.md` and `docs/strategy/`:

- **Control plane** — authoritative API enforcement (policy, audit, deterministic tools, entitlements).
- **Provider runtime adapter** — outbound model/provider connectivity (PyPI `exo-adapter-*`, `src/runtime/*`).
- **Customer bridge** — optional OpenAI-shaped `POST /v1/chat/completions` (`EXO_ENABLE_OPENAI_COMPAT_GATEWAY`) or a future thin SDK; same governance spine as native APIs.

Canonical links: [`docs/strategy/governed-execution-positioning.md`](../../strategy/governed-execution-positioning.md), [`docs/plans/control-plane-product-alignment-plan.md`](../../plans/control-plane-product-alignment-plan.md). Customer contracts: [`docs/api/customer-api-integration-guide.md`](../../api/customer-api-integration-guide.md).

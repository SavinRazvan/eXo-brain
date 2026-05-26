# Contributing to eXo-brain

Thanks for the interest. A few honest things first.

## What this project is

eXo-brain is an **independent reference implementation** of governed agentic AI
execution — policy gates, deterministic tool runtime, provider-neutral
orchestration. It is **maintained part-time by a single author**. See
[MAINTAINER_STATUS.md](MAINTAINER_STATUS.md) for the operating posture.

## What that means for contributions

- **PRs are welcome but reviewed slowly.** Expect days to weeks, not hours.
- **Architectural changes need a design-discussion issue first.** Don't open a
  big PR cold; talk through the change first so the review can stay focused.
- **No commitment to merge.** A high-quality PR may still be declined if it
  pulls scope away from the project's current direction. The
  [MAINTAINER_STATUS.md](MAINTAINER_STATUS.md) "what I will and will not
  accept" section is the operating filter.
- **No release schedule.** When a slice is merged, it is merged.

## How to file something useful

1. **Bug report** — use the issue template. Include reproducer, environment,
   expected vs actual behaviour, and (ideally) a failing test.
2. **Question** — use the issue template. Check
   [docs/strategy/](docs/strategy/), [docs/architecture/](docs/architecture/),
   and [README.md](README.md) first.
3. **Feature discussion** — use the issue template. Describe the problem, the
   user, the alternative considered, and how the proposal fits the
   architecture invariants in
   [docs/strategy/goal.md](docs/strategy/goal.md) §6.
4. **Security report** — **do not** open a public issue. See
   [SECURITY.md](SECURITY.md).

## How to send a PR

1. Fork, branch from `main` with a `feature/`, `fix/`, or `chore/` prefix.
2. Keep changes scoped. Smaller is better. If you cannot describe the PR in
   one sentence, split it.
3. Add or update tests under `tests/modules/<area>/`.
4. Run the gates locally before pushing:
   - `python -m pytest -q`
   - `python scripts/architecture/validate_layers.py`
   - `python scripts/architecture/scan_forbidden_imports.py`
5. Commit messages: see [.cursor/rules/commit-trailer-format.mdc](.cursor/rules/commit-trailer-format.mdc).
   For external contributors, the `Author:` and `GitHub-User:` trailers are
   not required, but a descriptive Conventional Commits style is.
6. Open the PR against `main`. Use the PR template.

## Code style

The source of truth is the existing config:

- `pyrightconfig.json` for static typing.
- `.flake8` for lint rules.
- File headers per
  [.cursor/rules/file-docstring-header-relations.mdc](.cursor/rules/file-docstring-header-relations.mdc).

If your editor disagrees with these files, the files win.

## Architectural invariants (do not violate)

- **No provider SDK imports outside `src/runtime/*adapter*` modules.** This is
  enforced by `scripts/architecture/scan_forbidden_imports.py`.
- **No path that can reach tool execution may bypass policy middleware.**
  Both the orchestrator and the deterministic tool executor evaluate
  `before_tool_call` and `after_tool_call` for defense in depth.
- **Capability + policy drive execution mode, never provider-name branching
  in core.**
- **Tenant isolation by construction.** Per-tenant registries are built in
  `TenantRuntimeFactory`; do not introduce global mutable state that crosses
  tenants.

If a PR violates any of these, the review will ask you to redesign.

## License

By contributing, you agree your contributions are licensed under the
[Apache License 2.0](LICENSE), the same as the rest of the project.

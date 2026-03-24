"""
File: validate_layers.py
Path: scripts/architecture/validate_layers.py
Role: Validate module boundaries, public APIs, and high-level layer guardrails.
Used By:
 - .github/workflows/architecture-fitness.yml
Depends On:
 - ast
 - pathlib
 - scripts/architecture/ast_app_state_guard.py
 - src/modules/contracts.py
Notes:
 - Boundary checks are strict for `src/modules/*` and selected global guardrails.
 - Prepends repo root to `sys.path` so `src.*` imports work in CI without `PYTHONPATH`.
 - Rejects getattr(<...>.app.state, ...) / getattr(application.state, ...) patterns that bypass the app.state rule.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = str(ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_ARCH_DIR = Path(__file__).resolve().parent
if str(_ARCH_DIR) not in sys.path:
    sys.path.insert(0, str(_ARCH_DIR))

import ast_app_state_guard  # noqa: E402

from src.modules.contracts import (
    allowed_dependencies_for_module,
    is_public_module_import,
    module_name_for_import,
    module_name_for_path,
)
SRC = ROOT / "src"
ALLOWED_APP_STATE_FILES = {
    "src/api/app.py",
    "src/api/bootstrap.py",
    "src/api/dependencies.py",
    "src/api/readiness.py",
    "src/api/startup.py",
    "src/modules/platform_bootstrap/service.py",
}

# Legacy tree files that must still obey module dependency rules (beyond src/modules/**).
_EXTRA_BOUNDARY_FILES = frozenset(
    {
        "src/api/readiness.py",
        "src/api/routers/prometheus_metrics.py",
    }
)


def _parse_file(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports_for_tree(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _validate_module_imports(*, rel: str, imports: list[str], violations: list[str]) -> None:
    if rel == "src/modules/contracts.py":
        return
    in_modules = rel.startswith("src/modules/")
    in_extra_boundary = rel in _EXTRA_BOUNDARY_FILES
    if not in_modules and not in_extra_boundary:
        return
    owner = module_name_for_path(rel)
    if owner is None:
        violations.append(f"{rel}: module file is not mapped in src/modules/contracts.py")
        return
    allowed = allowed_dependencies_for_module(owner)
    for imp in imports:
        imported_owner = module_name_for_import(imp)
        if imported_owner is None or imported_owner == owner:
            continue
        if imported_owner not in allowed:
            violations.append(
                f"{rel}: module '{owner}' must not depend on module '{imported_owner}' via import '{imp}'"
            )
        if imp.startswith("src.modules.") and not is_public_module_import(imp):
            violations.append(
                f"{rel}: cross-module import '{imp}' bypasses the target module public API"
            )


def main() -> int:
    violations: list[str] = []
    for py_file in SRC.rglob("*.py"):
        rel = py_file.relative_to(ROOT).as_posix()
        tree = _parse_file(py_file)
        imports = _imports_for_tree(tree)

        if rel.startswith("src/core/"):
            for imp in imports:
                if imp.startswith("src.integration"):
                    violations.append(f"{rel}: core must not import integration layer ({imp})")
                if imp.startswith("src.runtime.openai_agents_runtime"):
                    violations.append(f"{rel}: core must depend on runtime_adapter interfaces, not concrete adapters ({imp})")
        _validate_module_imports(rel=rel, imports=imports, violations=violations)
        if rel not in ALLOWED_APP_STATE_FILES and ast_app_state_guard.has_direct_app_state_access(tree):
            violations.append(f"{rel}: direct app.state access is reserved for bootstrap/startup/dependency wiring")
        if ast_app_state_guard.getattr_bypasses_app_state_guard(tree):
            violations.append(
                f"{rel}: getattr(..., on app.state / application.state) bypasses the app.state access guard; "
                "bind `st = <...>.state` then use direct attributes or getattr(st, ...)"
            )

    if violations:
        print("Layer validation failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Layer validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

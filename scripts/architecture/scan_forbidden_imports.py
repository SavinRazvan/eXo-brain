"""
File: scan_forbidden_imports.py
Path: scripts/architecture/scan_forbidden_imports.py
Role: Block provider SDK and transport framework imports outside allowed boundaries.
Used By:
 - .github/workflows/architecture-fitness.yml
Depends On:
 - ast
 - pathlib
Notes:
 - Provider SDK imports are allowed only inside runtime adapter modules.
 - Adapter packages under ``eXo_adapters/packages/``, ``moving_to_adapters_project/packages/``, or legacy ``packages/`` must not import monorepo ``src.*`` modules.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

# Provider SDK imports — allowed only in src/runtime/*adapter* files.
PROVIDER_SDK_PREFIXES = (
    "openai",
    "anthropic",
    "google.generativeai",
    "vertexai",
)

# Transport framework imports — allowed in src/runtime/*adapter* AND src/api/ files.
TRANSPORT_PREFIXES = (
    "fastapi",
    "flask",
    "quart",
)


def _imports_for_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _is_runtime_adapter_file(rel_path: str) -> bool:
    return rel_path.startswith("src/runtime/") and "adapter" in rel_path


def _is_api_file(rel_path: str) -> bool:
    """src/api/ is the designated transport boundary — FastAPI imports are allowed here."""
    return rel_path.startswith("src/api/")


def _is_adapter_package_file(rel_path: str) -> bool:
    # Staging: moving_to_adapters_project/packages/exo-adapter-*/src/...
    # Legacy: packages/exo-adapter-*/src/...
    return "/packages/exo-adapter-" in rel_path and "/src/" in rel_path


def _adapter_package_roots() -> list[Path]:
    roots: list[Path] = []
    for candidate in (
        ROOT / "eXo_adapters" / "packages",
        ROOT / "moving_to_adapters_project" / "packages",
        ROOT / "packages",
    ):
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def _is_forbidden_monorepo_import_for_adapter_package(module: str) -> bool:
    return module == "src" or module.startswith("src.")


def main() -> int:
    violations: list[str] = []
    for py_file in SRC.rglob("*.py"):
        rel = py_file.relative_to(ROOT).as_posix()
        is_adapter = _is_runtime_adapter_file(rel)
        is_api = _is_api_file(rel)
        for module in _imports_for_file(py_file):
            if module.startswith(PROVIDER_SDK_PREFIXES) and not is_adapter:
                violations.append(
                    f"{rel}: forbidden provider SDK import '{module}' outside runtime adapter boundary"
                )
            elif module.startswith(TRANSPORT_PREFIXES) and not (is_adapter or is_api):
                violations.append(
                    f"{rel}: forbidden transport import '{module}' outside api/adapter boundary"
                )

    seen: set[Path] = set()
    for pkg_root in _adapter_package_roots():
        for py_file in pkg_root.rglob("*.py"):
            if py_file in seen:
                continue
            rel = py_file.relative_to(ROOT).as_posix()
            if not _is_adapter_package_file(rel):
                continue
            seen.add(py_file)
            for module in _imports_for_file(py_file):
                if _is_forbidden_monorepo_import_for_adapter_package(module):
                    violations.append(
                        f"{rel}: forbidden monorepo import '{module}' inside adapter package boundary"
                    )

    if violations:
        print("Forbidden import scan failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Forbidden import scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

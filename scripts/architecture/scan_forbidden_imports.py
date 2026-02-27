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
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

FORBIDDEN_PREFIXES = (
    "openai",
    "anthropic",
    "google.generativeai",
    "vertexai",
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


def main() -> int:
    violations: list[str] = []
    for py_file in SRC.rglob("*.py"):
        rel = py_file.relative_to(ROOT).as_posix()
        allowed = _is_runtime_adapter_file(rel)
        for module in _imports_for_file(py_file):
            if module.startswith(FORBIDDEN_PREFIXES) and not allowed:
                violations.append(f"{rel}: forbidden import '{module}' outside runtime adapter boundary")

    if violations:
        print("Forbidden import scan failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Forbidden import scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

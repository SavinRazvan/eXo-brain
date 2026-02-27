"""
File: validate_layers.py
Path: scripts/architecture/validate_layers.py
Role: Validate high-level import boundaries to prevent architecture drift.
Used By:
 - .github/workflows/architecture-fitness.yml
Depends On:
 - ast
 - pathlib
Notes:
 - Keep rules conservative; expand as modules grow.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports_for_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend([alias.name for alias in node.names])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def main() -> int:
    violations: list[str] = []
    for py_file in SRC.rglob("*.py"):
        rel = py_file.relative_to(ROOT).as_posix()
        imports = _imports_for_file(py_file)

        if rel.startswith("src/core/"):
            for imp in imports:
                if imp.startswith("src.integration"):
                    violations.append(f"{rel}: core must not import integration layer ({imp})")
                if imp.startswith("src.runtime.openai_agents_runtime"):
                    violations.append(f"{rel}: core must depend on runtime_adapter interfaces, not concrete adapters ({imp})")

    if violations:
        print("Layer validation failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Layer validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
 - Portable adapter packages are authored in SavinRazvan/eXo_adapters (PyPI); not scanned in this repo.
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

    if violations:
        print("Forbidden import scan failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Forbidden import scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

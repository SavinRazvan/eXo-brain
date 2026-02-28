"""
File: conftest.py
Path: tests/conftest.py
Role: Auto-assign module markers and provide optional duplicate-name guardrails.
Used By:
 - pytest test collection
Depends On:
 - pytest
 - Python ast/pathlib standard library
Notes:
 - Module markers are inferred from `src.<module>` imports in each test file.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_KNOWN_MODULES: set[str] = {
    "access_control",
    "agents",
    "audit",
    "compliance",
    "config",
    "core",
    "identity",
    "integration",
    "mcp",
    "observability",
    "persistence",
    "policies",
    "resilience",
    "runtime",
    "schemas",
    "secrets",
    "tenancy",
    "tools",
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--enforce-unique-test-names-per-module",
        action="store_true",
        default=False,
        help="Fail if the same test function name appears multiple times in the same module marker bucket.",
    )


def _infer_src_modules(test_file: Path) -> set[str]:
    try:
        content = test_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return set()

    discovered: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name.startswith("src."):
                discovered.add(module_name.split(".", 2)[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src."):
                    discovered.add(alias.name.split(".", 2)[1])
    return discovered.intersection(_KNOWN_MODULES)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    file_modules_cache: dict[Path, set[str]] = {}
    test_name_index: dict[tuple[str, str], list[str]] = {}

    for item in items:
        item_path = Path(str(item.path))
        modules = file_modules_cache.setdefault(item_path, _infer_src_modules(item_path))
        markers: set[str] = set()
        if modules:
            for module_name in sorted(modules):
                marker = f"module_{module_name}"
                item.add_marker(getattr(pytest.mark, marker))
                markers.add(marker)
        else:
            item.add_marker(pytest.mark.module_unknown)
            markers.add("module_unknown")

        base_test_name = (item.originalname or item.name).split("[", 1)[0]
        for marker in markers:
            test_name_index.setdefault((marker, base_test_name), []).append(item.nodeid)

    if not config.getoption("--enforce-unique-test-names-per-module"):
        return

    duplicate_entries = {
        key: nodeids
        for key, nodeids in test_name_index.items()
        if len(nodeids) > 1 and key[0] != "module_unknown"
    }
    if duplicate_entries:
        lines = ["Duplicate test names detected in the same module bucket:"]
        for (marker, test_name), nodeids in sorted(duplicate_entries.items()):
            lines.append(f"- {marker}::{test_name}")
            for nodeid in nodeids:
                lines.append(f"  - {nodeid}")
        raise pytest.UsageError("\n".join(lines))

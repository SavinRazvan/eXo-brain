"""
File: conftest.py
Path: tests/conftest.py
Role: Auto-assign module markers, verify adapter wheels, optional duplicate-name guardrails.
Used By:
 - pytest test collection
Depends On:
 - pytest
 - tests/constants.py
Notes:
 - Module markers are inferred from `src.<module>` imports in each test file.
 - Session start fails fast when PyPI adapter pins from requirements.txt are missing or mismatched.
"""

from __future__ import annotations

import ast
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

from tests.constants import ADAPTER_DISTRIBUTIONS, ADAPTER_IMPORT_MODULES

_REPO_ROOT = Path(__file__).resolve().parents[1]

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


def _pinned_adapter_versions() -> dict[str, str]:
    req = (_REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    pins: dict[str, str] = {}
    for dist in ADAPTER_DISTRIBUTIONS:
        match = re.search(rf"^{re.escape(dist)}==(\S+)", req, re.MULTILINE)
        if match:
            pins[dist] = match.group(1)
    return pins


def pytest_sessionstart(session: pytest.Session) -> None:
    """Fail fast when any of the four adapter wheels are missing or wrong version."""
    del session
    pins = _pinned_adapter_versions()
    if len(pins) != len(ADAPTER_DISTRIBUTIONS):
        pytest.exit("requirements.txt must pin all four exo adapter distributions", returncode=2)

    errors: list[str] = []
    for dist, pinned in pins.items():
        try:
            installed = version(dist)
        except PackageNotFoundError:
            errors.append(f"{dist} not installed (pip install -r requirements.txt)")
            continue
        if installed != pinned:
            errors.append(
                f"{dist} installed {installed!r} != pinned {pinned!r} "
                "(run: bash scripts/dev/install_adapter_dependencies.sh)"
            )
            continue
        module_name = ADAPTER_IMPORT_MODULES[dist]
        try:
            __import__(module_name)
        except ImportError as exc:
            errors.append(f"{dist} import {module_name!r} failed: {exc}")

    if errors:
        pytest.exit("Adapter wheel preflight failed:\n  - " + "\n  - ".join(errors), returncode=2)


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

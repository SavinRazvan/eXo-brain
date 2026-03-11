"""
File: test_core_contracts_imports.py
Path: tests/packages/test_core_contracts_imports.py
Role: Verify new core contracts package exports load in-repo.
Used By:
 - CI test suite
Depends On:
 - packages/exo-brain-core-contracts
Notes:
 - Adds package src path at runtime because the package is not installed in editable mode in CI.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _add_package_path(package_dir: str) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    package_src = repo_root / "packages" / package_dir / "src"
    sys.path.insert(0, str(package_src))


def test_core_contracts_exports_load() -> None:
    _add_package_path("exo-brain-core-contracts")

    import exo_brain_core_contracts as contracts

    assert contracts.RuntimeAdapter is not None
    assert contracts.ToolCallContext is not None
    assert contracts.RuntimeEvent is not None

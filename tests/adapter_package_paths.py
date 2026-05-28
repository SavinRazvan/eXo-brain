"""
File: adapter_package_paths.py
Path: tests/adapter_package_paths.py
Role: Detect installed or local portable adapter packages for conformance tests.
Used By:
 - tests/packages/test_echo_adapter_conformance.py
 - tests/packages/test_openai_adapter_conformance.py
 - tests/modules/runtime/test_adapter_factory.py
Depends On:
 - importlib (installed wheels) or packages/repo_for_pipy (dev fallback)
Notes:
 - Prefer PyPI/editable installs; local src trees are dev-only fallback.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTRACTS_DIR = "exo-brain-core-contracts"
_MARKER = _CONTRACTS_DIR + "/pyproject.toml"
_PORTABLE_ADAPTER_PACKAGE_DIRS = (
    "exo-brain-adapter-sdk",
    "exo-adapter-echo",
    "exo-adapter-openai",
)


def packaged_adapters_installed() -> bool:
    """True when adapter wheels are importable (PyPI or editable install)."""
    return importlib.util.find_spec("exo_adapter_openai") is not None


def _local_adapter_workspace() -> Path | None:
    for candidate in (
        REPO_ROOT / "packages" / "repo_for_pipy" / "packages",
        REPO_ROOT / "eXo_adapters" / "packages",
        REPO_ROOT / "packages" / "eXo_adapters" / "packages",
        REPO_ROOT / "moving_to_adapters_project" / "packages",
        REPO_ROOT / "packages",
    ):
        if (candidate / _MARKER).is_file():
            return candidate
    return None


def local_portable_adapters_present() -> bool:
    if packaged_adapters_installed():
        return True
    workspace = _local_adapter_workspace()
    if workspace is None:
        return False
    return all((workspace / package_name / "src").is_dir() for package_name in _PORTABLE_ADAPTER_PACKAGE_DIRS)


def package_src(package_name: str) -> Path:
    """Return local src tree for sys.path injection (legacy dev fallback only)."""
    workspace = _local_adapter_workspace()
    if workspace is None:
        raise FileNotFoundError(
            "Portable adapter packages not found. Install with "
            "bash scripts/dev/install_adapter_dependencies.sh"
        )
    src_root = workspace / package_name / "src"
    if not src_root.is_dir():
        raise FileNotFoundError(f"Expected package src tree: {src_root}")
    return src_root

"""
File: adapter_package_paths.py
Path: tests/adapter_package_paths.py
Role: Locate optional local portable adapter package workspace for conformance tests.
Used By:
 - tests/packages/test_echo_adapter_conformance.py
 - tests/packages/test_openai_adapter_conformance.py
 - tests/modules/runtime/test_adapter_factory.py
Depends On:
 - Optional directory trees (see _local_adapter_workspace)
Notes:
 - Probe order matches scripts/packages/external_install_smoke.py _local_adapter_workspace().
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_CONTRACTS_DIR = "exo-brain-core-contracts"
_MARKER = _CONTRACTS_DIR + "/pyproject.toml"


def _local_adapter_workspace() -> Path | None:
    for candidate in (
        REPO_ROOT / "eXo_adapters" / "packages",
        REPO_ROOT / "packages" / "eXo_adapters" / "packages",
        REPO_ROOT / "moving_to_adapters_project" / "packages",
        REPO_ROOT / "packages",
    ):
        if (candidate / _MARKER).is_file():
            return candidate
    return None


def local_portable_adapters_present() -> bool:
    return _local_adapter_workspace() is not None


def package_src(package_name: str) -> Path:
    workspace = _local_adapter_workspace()
    if workspace is None:
        raise FileNotFoundError(
            "Portable adapter packages not found under eXo_adapters/packages, "
            "packages/eXo_adapters/packages, moving_to_adapters_project/packages, "
            "or legacy packages/."
        )
    src_root = workspace / package_name / "src"
    if not src_root.is_dir():
        raise FileNotFoundError(f"Expected package src tree: {src_root}")
    return src_root

"""
File: adapter_package_paths.py
Path: tests/adapter_package_paths.py
Role: Detect installed adapter packages for conformance tests.
Used By:
 - tests/packages/test_echo_adapter_conformance.py
 - tests/packages/test_openai_adapter_conformance.py
 - tests/modules/runtime/test_adapter_factory.py
Depends On:
 - importlib (installed wheels from PyPI)
Notes:
 - Adapter source lives in SavinRazvan/eXo_adapters; eXo-brain installs wheels via requirements.txt.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_MODULE_BY_DISTRIBUTION = {
    "exo-brain-core-contracts": "exo_brain_core_contracts",
    "exo-brain-adapter-sdk": "exo_brain_adapter_sdk",
    "exo-adapter-echo": "exo_adapter_echo",
    "exo-adapter-openai": "exo_adapter_openai",
}


def packaged_adapters_installed() -> bool:
    """True when adapter wheels are importable (PyPI install)."""
    return importlib.util.find_spec("exo_adapter_openai") is not None


def local_portable_adapters_present() -> bool:
    """Alias for CI skip guards — requires PyPI adapter wheels."""
    return packaged_adapters_installed()


def installed_package_root(distribution_name: str) -> Path:
    """Return the on-disk root directory for an installed distribution."""
    module_name = _MODULE_BY_DISTRIBUTION.get(distribution_name)
    if module_name is None:
        raise KeyError(f"Unknown distribution: {distribution_name}")
    mod = importlib.import_module(module_name)
    return Path(mod.__file__).resolve().parent


def package_src(package_name: str) -> Path:
    """Return installed package root (legacy name kept for test call sites)."""
    if not packaged_adapters_installed() and package_name != "exo-brain-core-contracts":
        raise FileNotFoundError(
            "Adapter packages not installed. Run: pip install -r requirements.txt"
        )
    return installed_package_root(package_name)

"""
File: test_openai_adapter_conformance.py
Path: tests/packages/test_openai_adapter_conformance.py
Role: Validate provider package wrapper and runtime contract conformance helper.
Used By:
 - CI test suite
Depends On:
 - packages/exo-brain-adapter-sdk
 - packages/exo-adapter-openai
Notes:
 - Contract check is structural and does not require network/API keys.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _add_package_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    paths = [
        repo_root / "packages" / "exo-brain-core-contracts" / "src",
        repo_root / "packages" / "exo-brain-adapter-sdk" / "src",
        repo_root / "packages" / "exo-adapter-openai" / "src",
    ]
    for path in reversed(paths):
        sys.path.insert(0, str(path))


def test_openai_adapter_package_conformance() -> None:
    _add_package_paths()

    from exo_adapter_openai import OpenAIAgentsRuntimeAdapter
    from exo_brain_adapter_sdk import assert_runtime_adapter_contract

    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    assert_runtime_adapter_contract(adapter)

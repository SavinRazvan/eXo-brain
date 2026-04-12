"""
File: test_core_contracts_imports.py
Path: tests/packages/test_core_contracts_imports.py
Role: Verify ``exo-brain-core-contracts`` (from pip / eXo_adapters) exports load in the control-plane env.
Used By:
 - CI test suite
Depends On:
 - exo_brain_core_contracts (requirements.txt → git or PyPI)
Notes:
 - No local ``packages/`` tree required; package is installed like any other dependency.
"""

from __future__ import annotations


def test_core_contracts_exports_load() -> None:
    import exo_brain_core_contracts as contracts

    assert contracts.RuntimeAdapter is not None
    assert contracts.ToolCallContext is not None
    assert contracts.RuntimeEvent is not None
    assert callable(contracts.RuntimeEvent.tool_intent)
    assert callable(contracts.blocked_result)

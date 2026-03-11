"""
File: __init__.py
Path: packages/exo-brain-adapter-sdk/src/exo_brain_adapter_sdk/conformance/__init__.py
Role: Conformance helper exports for adapter SDK.
Used By:
 - provider adapter tests
Depends On:
 - runtime_adapter_contract.py
Notes:
 - Keeps package import path stable.
"""

from exo_brain_adapter_sdk.conformance.runtime_adapter_contract import assert_runtime_adapter_contract

__all__ = ["assert_runtime_adapter_contract"]

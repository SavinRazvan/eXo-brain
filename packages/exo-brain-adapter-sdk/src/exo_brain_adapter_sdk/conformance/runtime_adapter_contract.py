"""
File: runtime_adapter_contract.py
Path: packages/exo-brain-adapter-sdk/src/exo_brain_adapter_sdk/conformance/runtime_adapter_contract.py
Role: Lightweight runtime adapter conformance assertions for provider packages.
Used By:
 - package-level adapter tests
Depends On:
 - inspect
Notes:
 - This is intentionally minimal and side-effect free.
"""

from __future__ import annotations

import inspect
from typing import Any


def assert_runtime_adapter_contract(adapter: Any) -> None:
    required_async = ("start_session", "run_turn", "submit_tool_results", "healthcheck")
    for method_name in required_async:
        fn = getattr(adapter, method_name, None)
        if fn is None:
            raise AssertionError(f"Missing required runtime adapter method: {method_name}")
        if not (inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)):
            raise AssertionError(f"Method must be async: {method_name}")

    capabilities = getattr(adapter, "get_capabilities", None)
    if capabilities is None or not callable(capabilities):
        raise AssertionError("Missing required runtime adapter method: get_capabilities")

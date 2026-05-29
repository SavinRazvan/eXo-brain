"""
File: test_echo_adapter_conformance.py
Path: tests/packages/test_echo_adapter_conformance.py
Role: Conformance tests for the portable exo-adapter-echo package.
Used By:
 - pytest
Depends On:
 - tests.adapter_package_paths
 - exo-brain-adapter-sdk, exo-adapter-echo (PyPI)
Notes:
 - Mirrors tests/packages/test_openai_adapter_conformance.py for a second external adapter.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.adapter_package_paths import installed_package_root, local_portable_adapters_present

requires_installed_adapters = pytest.mark.skipif(
    not local_portable_adapters_present(),
    reason="Install adapter packages: pip install -r requirements.txt",
)


@requires_installed_adapters
def test_echo_adapter_package_conformance() -> None:
    from exo_adapter_echo import EchoRuntimeAdapter
    from exo_brain_adapter_sdk import assert_runtime_adapter_contract

    adapter = EchoRuntimeAdapter(provider_id="echo-test")
    assert_runtime_adapter_contract(adapter)


@requires_installed_adapters
def test_echo_adapter_portability_smoke_run_turn() -> None:
    from exo_adapter_echo import EchoRuntimeAdapter

    adapter = EchoRuntimeAdapter(provider_id="echo-test")
    assert adapter.__class__.__module__.startswith("exo_adapter_echo.")

    async def _collect_event_types() -> list[str]:
        await adapter.start_session("sess-echo", metadata={"agent_id": "smoke-agent"})
        event_types: list[str] = []
        async for event in adapter.run_turn(
            session_id="sess-echo",
            user_input="hello",
            context={"run_id": "run-echo"},
        ):
            event_types.append(str(getattr(event.event_type, "value", event.event_type)))
        return event_types

    event_types = asyncio.run(_collect_event_types())
    assert "output_delta" in event_types
    assert "run_complete" in event_types


@requires_installed_adapters
def test_echo_package_has_no_monorepo_imports() -> None:
    base = installed_package_root("exo-adapter-echo")
    package_files = [
        base / "__init__.py",
        base / "runtime.py",
    ]
    for file_path in package_files:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith("from src."), f"Monorepo import found in {file_path}: {stripped}"
            assert not stripped.startswith("import src."), f"Monorepo import found in {file_path}: {stripped}"

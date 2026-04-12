"""
File: test_echo_adapter_conformance.py
Path: tests/packages/test_echo_adapter_conformance.py
Role: Conformance tests for the portable exo-adapter-echo package.
Used By:
 - pytest
Depends On:
 - tests.adapter_package_paths
 - exo-brain-adapter-sdk, exo-adapter-echo trees
Notes:
 - Mirrors tests/packages/test_openai_adapter_conformance.py for a second external adapter.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.adapter_package_paths import local_portable_adapters_present, package_src

requires_local_adapter_packages = pytest.mark.skipif(
    not local_portable_adapters_present(),
    reason="Portable adapter sources live in eXo_adapters; add a local packages/ tree or sibling checkout to run these tests.",
)


def _add_package_paths() -> None:
    paths = [
        package_src("exo-brain-core-contracts"),
        package_src("exo-brain-adapter-sdk"),
        package_src("exo-adapter-echo"),
    ]
    for path in reversed(paths):
        sys.path.insert(0, str(path))


@requires_local_adapter_packages
def test_echo_adapter_package_conformance() -> None:
    _add_package_paths()

    from exo_adapter_echo import EchoRuntimeAdapter
    from exo_brain_adapter_sdk import assert_runtime_adapter_contract

    adapter = EchoRuntimeAdapter(provider_id="echo-test")
    assert_runtime_adapter_contract(adapter)


@requires_local_adapter_packages
def test_echo_adapter_portability_smoke_run_turn() -> None:
    _add_package_paths()

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


@requires_local_adapter_packages
def test_echo_package_has_no_monorepo_imports() -> None:
    base = package_src("exo-adapter-echo") / "exo_adapter_echo"
    package_files = [
        base / "__init__.py",
        base / "runtime.py",
    ]
    for file_path in package_files:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith("from src."), f"Monorepo import found in {file_path}: {stripped}"
            assert not stripped.startswith("import src."), f"Monorepo import found in {file_path}: {stripped}"

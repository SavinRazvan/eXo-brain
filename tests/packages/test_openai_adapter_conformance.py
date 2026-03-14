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

import asyncio
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


def test_openai_adapter_load_adapter_factory() -> None:
    _add_package_paths()

    from exo_adapter_openai import load_adapter

    adapter = load_adapter(provider_id="openai-factory")
    assert adapter.get_capabilities().provider_id == "openai-factory"


def test_openai_adapter_package_has_no_monorepo_imports() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    package_files = [
        repo_root / "packages" / "exo-adapter-openai" / "src" / "exo_adapter_openai" / "__init__.py",
        repo_root / "packages" / "exo-adapter-openai" / "src" / "exo_adapter_openai" / "runtime.py",
        repo_root / "packages" / "exo-adapter-openai" / "src" / "exo_adapter_openai" / "tool_wiring.py",
    ]
    for file_path in package_files:
        for line in file_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            assert not stripped.startswith("from src."), f"Monorepo import found in {file_path}: {stripped}"
            assert not stripped.startswith("import src."), f"Monorepo import found in {file_path}: {stripped}"


def test_openai_adapter_portability_smoke_run_turn() -> None:
    _add_package_paths()

    from exo_adapter_openai import OpenAIAgentsRuntimeAdapter

    adapter = OpenAIAgentsRuntimeAdapter(provider_id="openai-test")
    assert adapter.__class__.__module__.startswith("exo_adapter_openai.")

    async def _collect_event_types() -> list[str]:
        await adapter.start_session("sess-portability", metadata={"agent_id": "smoke-agent"})
        event_types: list[str] = []
        async for event in adapter.run_turn(
            session_id="sess-portability",
            user_input="hello",
            context={"run_id": "run-portability"},
        ):
            event_types.append(str(getattr(event.event_type, "value", event.event_type)))
        return event_types

    event_types = asyncio.run(_collect_event_types())
    assert "output_delta" in event_types
    assert "run_complete" in event_types

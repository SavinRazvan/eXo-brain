"""
File: test_packaged_adapter_e2e.py
Path: tests/modules/runtime/test_packaged_adapter_e2e.py
Role: E2E checks that canonical adapter_class_ref loads installed wheels and runs governed echo turns.
Used By:
 - CI packages/runtime jobs after install_adapter_dependencies.sh
Depends On:
 - exo_adapter_echo, exo_adapter_openai
 - src/runtime/adapter_factory.py
Notes:
 - Echo path needs no API key; OpenAI load is structural only.
"""

from __future__ import annotations

import asyncio

import pytest

from tests.adapter_package_paths import packaged_adapters_installed

from src.runtime.adapter_factory import (
    ECHO_ADAPTER_CANONICAL_CLASS_REF,
    OPENAI_ADAPTER_CANONICAL_CLASS_REF,
    load_adapter,
)

requires_packaged_adapters = pytest.mark.skipif(
    not packaged_adapters_installed(),
    reason="Install adapter packages: bash scripts/dev/install_adapter_dependencies.sh",
)


@requires_packaged_adapters
def test_factory_loads_packaged_openai_class() -> None:
    from exo_adapter_openai.runtime import OpenAIAgentsRuntimeAdapter

    adapter = load_adapter(OPENAI_ADAPTER_CANONICAL_CLASS_REF, provider_id="openai-e2e")
    assert isinstance(adapter, OpenAIAgentsRuntimeAdapter)
    assert adapter.get_capabilities().provider_id == "openai-e2e"


@requires_packaged_adapters
def test_factory_loads_packaged_echo_class() -> None:
    from exo_adapter_echo.runtime import EchoRuntimeAdapter

    adapter = load_adapter(ECHO_ADAPTER_CANONICAL_CLASS_REF, provider_id="echo-e2e")
    assert isinstance(adapter, EchoRuntimeAdapter)
    assert adapter.get_capabilities().provider_id == "echo-e2e"


@requires_packaged_adapters
def test_echo_governed_turn_emits_terminal_event() -> None:
    from exo_brain_core_contracts.events import RuntimeEventType

    adapter = load_adapter(ECHO_ADAPTER_CANONICAL_CLASS_REF, provider_id="echo-governed")

    async def _collect() -> list:
        events = []
        async for event in adapter.run_turn(
            "sess-echo-governed",
            "ping",
            {"run_id": "run-echo-governed", "tenant_id": "t1"},
        ):
            events.append(event)
        return events

    events = asyncio.run(_collect())
    assert events, "echo adapter should emit at least one RuntimeEvent"
    types = {e.event_type for e in events}
    assert RuntimeEventType.RUN_COMPLETE in types or RuntimeEventType.ASSISTANT_MESSAGE in types

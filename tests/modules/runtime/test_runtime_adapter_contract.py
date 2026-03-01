"""
File: test_runtime_adapter_contract.py
Path: tests/modules/runtime/test_runtime_adapter_contract.py
Role: Contract tests for runtime adapters.
Used By:
 - pytest
Depends On:
 - src/runtime/openai_agents_runtime.py
 - src/runtime/runtime_adapter.py
Notes:
 - Ensures adapters implement required interface behavior.
"""

import asyncio
from collections.abc import AsyncIterator

from src.runtime.custom_runtime import CustomRuntimeAdapter
from src.runtime.openai_agents_runtime import OpenAIAgentsRuntimeAdapter
from src.runtime.openai_compatible_runtime import OpenAICompatibleRuntimeAdapter
from src.runtime.runtime_adapter import RuntimeAdapter
from src.schemas.events import RuntimeEventType


def test_openai_adapter_implements_runtime_interface() -> None:
    adapter = OpenAIAgentsRuntimeAdapter()
    assert isinstance(adapter, RuntimeAdapter)


def test_openai_adapter_contract_methods_work() -> None:
    adapter = OpenAIAgentsRuntimeAdapter()

    async def _run() -> None:
        session = await adapter.start_session("sess_contract", metadata={"source": "test"})
        assert session.session_id == "sess_contract"
        assert adapter.get_capabilities().provider_id == "openai"
        assert (await adapter.healthcheck()).state.value == "healthy"

        stream = adapter.run_turn("sess_contract", "hello", {"run_id": "run_contract"})
        assert isinstance(stream, AsyncIterator)

    asyncio.run(_run())


def test_openai_compatible_adapter_contract_methods_work() -> None:
    adapter = OpenAICompatibleRuntimeAdapter()

    async def _run() -> None:
        session = await adapter.start_session("sess_compatible", metadata={"source": "test"})
        assert session.provider_id == "openai_compatible"
        assert adapter.get_capabilities().supports_openai_compatible_api is True
        assert (await adapter.healthcheck()).state.value == "healthy"

        stream = adapter.run_turn("sess_compatible", "hello", {"run_id": "run_compatible"})
        assert isinstance(stream, AsyncIterator)

    asyncio.run(_run())


def test_custom_adapter_contract_methods_work() -> None:
    adapter = CustomRuntimeAdapter()

    async def _run() -> None:
        session = await adapter.start_session("sess_custom", metadata={"source": "test"})
        assert session.provider_id == "custom"
        assert adapter.get_capabilities().provider_id == "custom"
        assert (await adapter.healthcheck()).state.value == "healthy"

        stream = adapter.run_turn("sess_custom", "hello", {"run_id": "run_custom"})
        assert isinstance(stream, AsyncIterator)

    asyncio.run(_run())


def test_runtime_adapters_normalize_turn_errors_for_invalid_user_input() -> None:
    adapters = (
        OpenAIAgentsRuntimeAdapter(),
        OpenAICompatibleRuntimeAdapter(),
        CustomRuntimeAdapter(),
    )

    async def _run() -> None:
        for adapter in adapters:
            await adapter.start_session("sess_bad_turn", metadata={"source": "test"})
            events = [
                event
                async for event in adapter.run_turn(
                    "sess_bad_turn",
                    {"text": "hello"},  # type: ignore[arg-type]
                    {"run_id": "run_bad_turn"},
                )
            ]
            assert events
            assert events[-1].event_type == RuntimeEventType.ERROR
            assert events[-1].payload.get("code") == "RUNTIME_TURN_ERROR"

    asyncio.run(_run())


def test_runtime_adapters_normalize_submit_tool_result_errors() -> None:
    adapters = (
        OpenAIAgentsRuntimeAdapter(),
        OpenAICompatibleRuntimeAdapter(),
        CustomRuntimeAdapter(),
    )

    async def _run() -> None:
        for adapter in adapters:
            await adapter.start_session("sess_bad_result", metadata={"source": "test"})
            events = [event async for event in adapter.submit_tool_results("sess_bad_result", "run_bad_result", None)]  # type: ignore[arg-type]
            assert events
            assert events[-1].event_type == RuntimeEventType.ERROR
            assert events[-1].payload.get("code") == "RUNTIME_TOOL_RESULT_ERROR"

    asyncio.run(_run())


def test_openai_agents_adapter_normalizes_malformed_planned_tool_call() -> None:
    adapter = OpenAIAgentsRuntimeAdapter()

    async def _run() -> None:
        await adapter.start_session("sess_bad_planned_call", metadata={"source": "test"})
        events = [
            event
            async for event in adapter.run_turn(
                "sess_bad_planned_call",
                "hello",
                {"run_id": "run_bad_planned_call", "planned_tool_call": {"arguments": {"x": 1}}},
            )
        ]
        assert events[-1].event_type == RuntimeEventType.ERROR
        assert events[-1].payload.get("code") == "RUNTIME_TURN_ERROR"

    asyncio.run(_run())
